"""通过双人 Web 界面验证 1007 对局的十一回合。"""

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import sys

from playwright.sync_api import BrowserType, Page, sync_playwright


CASE_DIR = Path(__file__).resolve().parent
RESULT_PATH = CASE_DIR / "1007-results.json"
CDP_PORTS = (9222, 9223)


def open_pages(chromium: BrowserType, browsers: ExitStack, use_cdp: bool) -> tuple[Page, Page]:
    """创建两个独立会话，或连接已打开的双窗口。"""
    if use_cdp:
        pages = []
        for port in CDP_PORTS:
            browser = chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=5000)
            browsers.callback(browser.close)
            context = browser.contexts[0]
            pages.append(context.pages[0] if context.pages else context.new_page())
        return pages[0], pages[1]

    browser = chromium.launch(channel="chrome")
    browsers.callback(browser.close)
    return browser.new_page(), browser.new_page()


def prepare(pages: tuple[Page, Page], base_url: str) -> None:
    """导入双方阵容、创建房间并确认首发。"""
    for page, side in zip(pages, ("A", "B")):
        roster = (CASE_DIR / f"1007{side}.json").read_text(encoding="utf-8")
        page.set_default_timeout(15_000)
        page.goto(base_url.rstrip("/") + "/", wait_until="domcontentloaded")
        page.locator("#rstBtn").click()
        page.locator("#roster-code").fill(roster)
        page.locator("#import-roster").click()
        page.get_by_text("阵容导入成功", exact=True).wait_for()

    a, b = pages
    a.locator("#start").click()
    a.get_by_role("button", name="确认首发", exact=True).wait_for()
    b.locator("#battle-code").fill(a.locator("#battle-code").input_value())
    b.locator("#join").click()
    b.get_by_role("button", name="确认首发", exact=True).wait_for()
    a.locator("#start").click()
    b.locator("#start").click()


class BattleCase:
    """执行对局并汇总双方断言和快照。"""

    def __init__(self, pages: tuple[Page, Page]) -> None:
        """保存页面与报告数据。"""
        self.pages = pages
        self.failures: list[str] = []
        self.snapshots: list[dict] = []

    def save_results(self) -> None:
        """以 UTF-8 保存报告。"""
        results = {"failures": self.failures, "snapshots": self.snapshots}
        RESULT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    def snapshot(self, label: str) -> list[dict]:
        """保存双方界面数据和原始事件，排除身份令牌。"""
        sides = [
            page.evaluate("""async () => {
                const { state } = await import('/static/state.js');
                const { battle_id, turn, phase, decision_index, terminal, winner } = state.battle;
                const fields = ['name', 'index', 'active', 'types', 'hp', 'max_hp', 'energy',
                    'fainted', 'ability', 'statuses', 'stats', 'modifiers', 'skills'];
                const teams = Object.fromEntries(['own', 'opponent'].map(side => [side,
                    state.teams[side].map(item => Object.fromEntries(
                        fields.filter(key => key in item).map(key => [key, item[key]])))]));
                return {
                    battle: { battle_id, turn, phase, decision_index, terminal, winner },
                    teams, shared: state.shared, events: state.events, display: state.display,
                    log: document.querySelector('#events').innerText,
                };
            }""")
            for page in self.pages
        ]
        self.snapshots.append({"label": label, "sides": sides})
        self.save_results()
        return sides

    def check(self, condition: bool, message: str) -> None:
        """记录断言失败并继续执行后续回合。"""
        if not condition:
            self.failures.append(message)
            print(message, file=sys.stderr)

    def assert_text(self, text: str, patterns: tuple[str, ...], name: str, *, hidden: tuple[str, ...] = ()) -> None:
        """验证文本中应显示和应隐藏的内容。"""
        for pattern in patterns:
            self.check(re.search(pattern, text) is not None, f"{name} 缺少 /{pattern}/；实际：{text}")
        for pattern in hidden:
            self.check(re.search(pattern, text) is None, f"{name} 应隐藏 /{pattern}/；实际：{text}")

    def assert_skill_detail(self, text: str, expected: dict[str, int], name: str) -> None:
        """检查技能数值和缺失字段，伤害允许误差 1。"""
        labels = {"power": "威力", "damage": "造成", "consume": "能耗", "rest": "剩余能量"}
        for field, value in expected.items():
            label = labels[field]
            match = re.search(rf"{label}\s*(\d+(?:\.\d+)?)", text)
            actual = float(match[1]) if match else None
            tolerance = 1 if field == "damage" else 0
            self.check(
                actual is not None and abs(actual - value) <= tolerance,
                f"{name} {label}异常：实际 {actual}，期望 {value}",
            )

    def ready(self, turn: int) -> None:
        """等待双方回合号同步且结算完成，包括力竭换宠阶段。"""
        for page in self.pages:
            page.locator("#turn").filter(has_text=re.compile(rf"^{turn}$")).wait_for()
            page.wait_for_function("""() => {
                const lock = document.querySelector('#lock-state');
                return lock && lock.textContent.trim() !== '正在结算';
            }""")

    def event_text(self, page: Page, event_type: str, turn: int, side: str) -> str:
        """按事件 ID 读取战报行，单独报告缺失和重复。"""
        event_id = f"{event_type}-{turn}-{side}"
        row = page.locator(f"#{event_id}")
        count = row.count()
        self.check(count == 1, f"缺少或重复战报：{event_id}")
        return row.inner_text() if count == 1 else ""

    def verify_effect_tip(self, page: Page, prefix: str, name: str, description: str) -> None:
        """检查特性状态标记和悬浮描述。"""
        badge = page.locator(f"#{prefix}-effects .field-effect").filter(has_text=name)
        actual = badge.get_attribute("data-effect-description") or ""
        self.assert_text(actual, (description,), f"{name} 特性描述")
        badge.hover()
        self.assert_text(page.locator("#skill-tooltip").inner_text(), (description,), f"{name} 悬浮描述")
        page.locator("#turn").hover()

    def verify_skills(self, turn: int, skills: tuple[str, str], details: tuple[dict, dict]) -> None:
        """按双方视角验证选招可见性和结算数值。"""
        for index, (seat, page) in enumerate(zip("AB", self.pages)):
            name = f"第{turn}回合{seat}视角"
            self.assert_text(self.event_text(page, "selection", turn, "a"), (re.escape(skills[index]),), name)
            self.assert_text(
                self.event_text(page, "selection", turn, "b"), ("完成",), name,
                hidden=(re.escape(skills[1 - index]),),
            )
            # 结算事件使用下一回合号，双方页面均将自己映射为 a。
            for skill_index, (skill, detail) in enumerate(zip(skills, details)):
                side = "a" if index == skill_index else "b"
                text = self.event_text(page, "skill", turn + 1, side)
                self.assert_text(text, (re.escape(skill),), name)
                self.assert_skill_detail(text, detail, f"{name} {skill}")

    def act(self, page: Page, action: str | int) -> None:
        """提交技能、聚能或指定阵容槽位的换宠。"""
        if isinstance(action, int):
            replacement = page.locator("#phase").inner_text() == "REPLACEMENT"
            page.locator('[data-action="creature"]').click()
            page.locator(f'[data-drawer-switch="{action}"]').click()
            if replacement:
                # 力竭换宠不增加回合号，先等双方离开换宠阶段。
                for target in self.pages:
                    target.wait_for_function("() => document.querySelector('#phase').textContent !== 'REPLACEMENT'")
                self.ready(int(page.locator("#turn").inner_text()))
        elif action == "聚能":
            page.locator("#charge").click()
        else:
            page.locator(f'[data-skill-name="{action}"]').click()

    def resolve_round(
        self,
        turn: int,
        action_a: str | int,
        action_b: str | int,
        *,
        skills: tuple[tuple[str, dict], ...],
        patterns: tuple[str, ...],
        mp_a: int | None = None,
    ) -> None:
        """执行一回合并验证双方战报、快照和奉献值。"""
        self.act(self.pages[0], action_a)
        self.act(self.pages[1], action_b)
        self.ready(turn + 1)
        for seat, page in zip("ab", self.pages):
            log = page.locator("#events .event-row").evaluate_all(
                r"""(nodes, turn) => nodes.filter(node => node.id.split('-')[1] === String(turn))
                    .map(node => node.id + ': ' + node.innerText).join('\n')""",
                turn + 1,
            )
            view = f"第{turn}回合{seat.upper()}视角"
            print(f"{view}\n{log}")
            for actor, detail in skills:
                visible_side = "a" if seat == actor else "b"
                text = self.event_text(page, "skill", turn + 1, visible_side)
                self.assert_skill_detail(text, detail, f"{view}（{actor.upper()}方技能）")
            self.assert_text(log, patterns, view)

        sides = self.snapshot(f"第{turn}回合结算")
        if mp_a is not None:
            own_mp = sides[0]["shared"]["mp"]["own"]
            opponent_mp = sides[1]["shared"]["mp"]["opponent"]
            self.check(
                own_mp == opponent_mp == mp_a,
                f"第{turn}回合A方MP异常：A视角 {own_mp}，B视角 {opponent_mp}，期望 {mp_a}",
            )

    def opening_rounds(self) -> None:
        """验证前三回合的选招隐藏、特性、换宠和冻结。"""
        a, b = self.pages
        self.ready(1)
        self.act(a, "火焰箭")
        self.act(b, "霜降")
        self.ready(2)
        self.verify_skills(1, ("火焰箭", "霜降"), (
            {"power": 160, "damage": 192, "consume": 2, "rest": 10},
            {"consume": 1, "rest": 9},
        ))
        self.assert_text(
            self.event_text(a, "ability", 2, "a"),
            ("特性：最好的伙伴", "迪莫", r"能量\+2", r"最好的伙伴\+1层"),
            "第1回合最好的伙伴",
        )
        self.assert_text(
            self.event_text(a, "ability", 2, "b"),
            ("迪莫", "捉迷藏", r"全部技能能耗\+1"),
            "第1回合捉迷藏",
        )
        state = self.event_text(a, "state_change", 2, "a")
        changes = ("全技能能耗 0→1", "冻结 0→4", "最好的伙伴 0→1")
        self.assert_text(state, changes, "第1回合迪莫状态")
        self.check(state.count("→") == len(changes), f"第1回合迪莫状态变化数量异常；实际：{state}")
        self.check(a.locator("#state_change-2-b").count() == 0, "第1回合大耳帽兜不应有状态变化记录")

        self.act(b, 1)
        self.act(a, "闪光冲击")
        self.ready(3)
        for page, side_a, prefix_b in ((a, "a", "enemy"), (b, "b", "own")):
            name = page.locator(f"#{prefix_b}-active-name").inner_text()
            self.assert_text(name, ("^尖嘴狐仙$",), "第2回合换宠")
            skill = self.event_text(page, "skill", 3, side_a)
            self.assert_text(skill, ("闪光冲击", "抵抗", "尖嘴狐仙生命"), "第2回合闪光冲击")
            self.assert_skill_detail(skill, {"damage": 80, "consume": 4}, "第2回合闪光冲击")

        self.act(a, "火焰箭")
        self.act(b, "爆裂飞弹")
        self.ready(4)
        self.verify_skills(3, ("火焰箭", "爆裂飞弹"), (
            {"damage": 206, "consume": 3},
            {"damage": 124, "consume": 7},
        ))
        for page, side_a, side_b, prefix_a in ((a, "a", "b", "own"), (b, "b", "a", "enemy")):
            self.assert_text(self.event_text(page, "skill", 4, side_a), ("克制", "尖嘴狐仙生命"), "第3回合火焰箭")
            self.assert_text(self.event_text(page, "skill", 4, side_b), ("迪莫生命",), "第3回合爆裂飞弹")
            self.assert_text(self.event_text(page, "state_change", 4, side_a), ("迪莫", "冻结 4→6"), "第3回合冻结")
            freeze = page.locator(f"#{prefix_a}-freeze-text").inner_text()
            self.assert_text(freeze, ("^冻结 6 层",), "第4回合迪莫冻结显示")

    def middle_rounds(self) -> None:
        """验证第四至第八回合的状态、聚能及迪莫力竭。"""
        a, b = self.pages
        self.resolve_round(4, "火焰箭", 4, skills=(("a", {"damage": 95, "consume": 3}),), patterns=("冻土", "2层"))
        self.verify_effect_tip(b, "own", "冻土", "地系技能威力")

        self.resolve_round(5, "聚能", "霜冻", skills=(("b", {"consume": 1}),), patterns=("魔防降低 0→10",))
        self.assert_text(a.locator("#own-energy").inner_text(), ("^能量 7$",), "第5回合聚能")
        self.assert_text(a.locator("#own-effects").inner_text(), (r"魔防\s*-10\s*10%",), "第5回合魔防降低显示")

        self.resolve_round(
            6, "棘突", "冰雹",
            skills=(("a", {"damage": 267, "consume": 4}), ("b", {"damage": 80, "consume": 4})),
            patterns=("最好的伙伴", r"能量\+2", "最好的伙伴 2→3"),
        )
        self.resolve_round(
            7, "棘突", 3,
            skills=(("a", {"damage": 320, "consume": 4}),),
            patterns=("克制", r"能量\+2", "最好的伙伴 3→4"),
        )
        # 四层最好的伙伴参与防御时，按伤害公式计算为 96。
        self.resolve_round(
            8, "聚能", "超导", skills=(("b", {"damage": 96, "consume": 1}),), patterns=("力竭",), mp_a=3,
        )
        self.assert_text(b.locator("#enemy-active-name").inner_text(), ("^迪莫$",), "第8回合对手保持力竭迪莫")
        self.assert_text(a.locator("#own-energy").inner_text(), ("^能量 8$",), "第8回合聚能")

    def closing_rounds(self) -> None:
        """验证第九至第十一回合的中毒、攻击应对、特性和退化。"""
        a, b = self.pages
        self.act(a, 2)
        self.snapshot("第9回合召唤蹦蹦花")
        self.resolve_round(
            9, "针刺射击", 2, skills=(("a", {"damage": 90, "consume": 3}),), patterns=("中毒 0→2",),
        )
        self.assert_text(a.locator("#own-energy").inner_text(), ("^能量 10$",), "第9回合换宠回能")
        self.assert_text(b.locator("#own-hp-text").inner_text(), ("^374 / 493$",), "第9回合中毒扣血")

        self.resolve_round(
            10, "剧毒", "暗突袭", skills=(("b", {"damage": 486, "consume": 4}),),
            patterns=("生命 374→493", r"恶魔的晚宴\+5层"), mp_a=2,
        )
        self.check(a.locator("#skill-11-a").count() == 0, "第10回合剧毒应被应对且不执行")
        self.assert_text(b.locator("#own-hp-text").inner_text(), ("^464 / 493$",), "第10回合中毒扣血")
        self.assert_text(b.locator("#own-effects").inner_text(), (r"中毒\s*2 层",), "第10回合中毒保持2层")
        self.assert_text(a.locator("#enemy-active-name").inner_text(), ("乌拉塔",), "第10回合敌方在场")
        self.assert_text(b.locator("#enemy-active-name").inner_text(), ("蹦蹦花",), "第10回合对手保持力竭蹦蹦花")
        for page, prefix in ((a, "enemy"), (b, "own")):
            effects = page.locator(f"#{prefix}-effects")
            self.assert_text(
                effects.inner_text(), (r"恶魔的晚宴\s*5 层",), "恶魔的晚宴完整状态",
                hidden=(r"攻击\s*5", r"魔攻\s*5"),
            )
            self.verify_effect_tip(page, prefix, "恶魔的晚宴", "击败")
            poison = effects.locator(".field-effect").filter(has_text="中毒")
            self.check(poison.get_attribute("data-effect-tip") is None, "中毒普通状态不应显示描述")

        self.act(a, 4)
        self.snapshot("第11回合召唤寒音蛇")
        self.assert_text(a.locator("#own-effects").inner_text(), (r"拨浪鼓\s*2 层",), "第11回合入场")
        self.resolve_round(
            11, "撒娇", "极限撕裂",
            skills=(("a", {"damage": 429, "consume": 3}), ("b", {"damage": 1021})),
            patterns=("143/段 × 3", "古钟蛇", "萌化", "恶魔的晚宴", "力竭"), mp_a=1,
        )
        self.assert_text(a.locator("#own-effects").inner_text(), (r"全技能威力\s*10",), "第11回合撒娇全技能威力")
        self.assert_text(a.locator("#own-active-name").inner_text(), ("^古钟蛇$",), "第11回合退化")
        self.assert_text(a.locator("#own-hp-text").inner_text(), ("^0 /",), "第11回合力竭")
        self.assert_text(b.locator("#enemy-active-name").inner_text(), ("^古钟蛇$",), "第11回合对手保持力竭古钟蛇")
        self.assert_text(b.locator("#own-effects").inner_text(), (r"恶魔的晚宴\s*10 层",), "恶魔的晚宴累计10层")
        self.assert_text(b.locator("#own-hp-text").inner_text(), ("^6 / 493$",), "第11回合中毒扣血")


def main() -> int:
    """运行用例并根据断言结果返回退出码。"""
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    base_url = os.getenv("NRC_TEST_URL") or "http://127.0.0.1:8767"
    with sync_playwright() as playwright, ExitStack() as browsers:
        pages = open_pages(playwright.chromium, browsers, True)
        case = BattleCase(pages)
        try:
            prepare(pages, base_url)
            case.opening_rounds()
            case.middle_rounds()
            case.closing_rounds()
        finally:
            case.save_results()

    print("十一回合执行完成。输入阵容里没有古拉多，结束于古钟蛇力竭。")
    if case.failures:
        print(f"共 {len(case.failures)} 项验证失败。", file=sys.stderr)
        return 1
    print("全部验证通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
