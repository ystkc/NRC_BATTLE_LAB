# T02 问题记录

本目录只审计，不改业务。T06-I15、T10-I01、T05-I03/I09与T03公式/复制问题均保留接口证据，不重复计主问题。

## T02-I01｜确认缺陷｜P1｜构造输入中的力竭精灵被复活

- 主责协同：T02构造主责；T03模型默认哨兵接口协同
- 规则依据/原文行号：data/README.md:30,35；nrc_core/schema.py CreatureState.hp/status 明确输入；GAME_RULE力竭
- 代码位置：nrc_platform/builder.py:459-487；nrc_core/models.py:354-364
- 最小输入步骤：完整六维HP1000，state.hp=0、status=fainted，正式BattleBuilder.build。另以真实一窝蜂/虫群鼓舞和其学习表前4技（乘风/信息素/借用/倾泻）复核，仍复活；附I01_real_species_control输入输出。
- 预期与实际：应保留HP0与力竭；实际HP1000、status=normal、is_fainted=False。builder将0传入Pokemon默认哨兵初始化后未还原，也完全忽略state.status。
- 影响范围：显式初始残血/力竭输入、需要保留已知状态的构造边界；不泛化到runtime pickle导入。
- 证据：`probe.py` 实际运行；`probe_output.json#I01_zero_hp`。

## T02-I02｜确认缺陷｜P1｜六项正资质被完整接受，缺少最多三项校验

- 主责协同：T02输入校验主责，T03公式协同
- 规则依据/原文行号：data/属性数值计算.md:30（每个精灵最多拥有三项大于零的资质值）
- 代码位置：nrc_platform/builder.py:318-338,363-365,474-487,589-647
- 最小输入步骤：base.individual_values六项全部8，提供完整六维隔离公式，正式build。
- 预期与实际：应拒绝六项正资质；实际六项iv_*均8且无异常。这里只核最多三项约束，绝不裁决文档6倍与+8→+40冲突。
- 影响范围：所有显式资质输入，非法组合可进入公式；与T03 Float16/倍数问题不同。
- 证据：`probe.py` 实际运行；`probe_output.json#I02_six_positive_iv`。

## T02-I03｜确认缺陷｜P2｜neutral/zero模式实际套用非中性坦率性格

- 主责协同：T02默认解析主责；P2内部协议/说明偏差
- 规则依据/原文行号：data/属性数值计算.md:6-22（坦率位于生命-/物防+，分别-10%/+20%）；builder的attribute_assumption协议
- 代码位置：nrc_platform/builder.py:354-362,398-411
- 最小输入步骤：只提供HP1000，metadata.attribute_assumption=neutral；物防种族27、资质0。
- 预期与实际：neutral/zero标记应代表无性格修正；实际记录assumption:neutral但nature=坦率、物防98。独立无性格公式round_half_up(round_half_up(27×1.1+10)×1)+50=90；坦率则40×1.2+50=98。游戏没有中性性格，若产品只想任选性格，至少不能将此输出标为neutral。
- 影响范围：单HP快捷输入被强制切neutral；zero/all_zero和无分布fallback同样使用坦率。默认应如何选择性格仍另列Q02，不从本问题强推产品默认。
- 证据：`probe.py` 实际运行；`probe_output.json#I03_neutral_nature`。

## T02-I04｜确认缺陷｜P2｜核心可解析的技能ID被建造校验拒绝，名称路径又重写ID

- 主责协同：T02平台结构化协议主责
- 规则依据/原文行号：nrc_core/schema.py:SkillSlotInput.skill_id/name；nrc_core/catalog.py:CoreCatalog.get_skill支持ID；nrc_platform/builder.py接口
- 代码位置：nrc_platform/builder.py:442-453,586-587,630-633
- 最小输入步骤：拍击目录ID skill_000303；对照catalog.get_skill(ID)，再以skills=[{skill_id:ID}]正式build。
- 预期与实际：目录能解析该ID为拍击；build先用names-only集合拒绝unknown skill。仅传name时又将目录稳定ID重写为拍击。应保持名称/ID两种协议一致并保留稳定标识。
- 影响范围：所有ID-only输入、需要目录ID的下游关联；目前常用slot动作仍可执行，不夸大为全技能不可用。
- 证据：`probe.py` 实际运行；`probe_output.json#I04_id_only`。

## T02-I05｜确认缺陷｜P1｜输入中多个同属性增益被后项覆盖

- 主责协同：T02状态注入主责，T03状态模型协同
- 规则依据/原文行号：data/伤害数值计算.md:15（同方加成和减弱同时存在、层数叠加）
- 代码位置：nrc_platform/builder.py:524-538
- 最小输入步骤：buffs=[物攻10%×2,物攻10%×3]，debuffs={atk:2}，基础物攻100。
- 预期与实际：应保留五层加成和两层减弱，atk_up=.5、atk_down=.2；实际atk_up=.3、atk_down=.2，有效物攻108.3333而非125。每条setattr覆盖前条而非合并。
- 影响范围：同一属性由多个条目给出的输入；增/减两桶本身并存通过。100层不封顶的输入端证据另关联T03-I03，避免重复主问题。
- 证据：`probe.py` 实际运行；`probe_output.json#I05_duplicate_buff`。

## T02-I06｜确认缺陷｜P2｜属性值不识别时静默改为普通

- 主责协同：T02类型适配主责
- 规则依据/原文行号：nrc_core/models.py Type枚举；nrc_platform/catalog.py _TYPE_ALIASES；AGENTS未知机制不静默降级
- 代码位置：nrc_platform/builder.py:422-429
- 最小输入步骤：完整构造输入base.attributes=[fire,water]（核心Type.value与目录解析均使用/接受的名称）。
- 预期与实际：应识别火/水，或按明确中文输入契约拒绝；实际接受后变成normal/normal，既不保留输入也不报错。中文18系正式目录装载转换已独立通过，不能据此掩盖该显式输入路径。
- 影响范围：英文核心枚举回填、拼写错误和未知类型；影响克制、本系与免疫。P2输入适配缺陷，具体公开输入枚举约束另请明确。
- 证据：`probe.py` 实际运行；`probe_output.json#I06_english_combat_types`。

## T02-I07｜确认缺陷｜P2｜嵌套base类型未拒绝，预览请求落入AttributeError

- 主责协同：T02输入主责；T12 HTTP协同
- 规则依据/原文行号：nrc_platform/input.py merge_creature_spec映射协议；HTTP预览结构化参数错误约定（T12端到端）
- 代码位置：nrc_platform/input.py:35-49；rooms.py:282-291；codec.py:66-88
- 最小输入步骤：RoomService.pokemon_preview({name:迪莫,base:invalid})；并测base=[1]、3。
- 预期与实际：应以结构化参数错误拒绝。merge将非Mapping的base原样交给下游，三个输入分别触发str/list/int没有get的AttributeError；T12实际HTTP返回500。修正应在输入边界或统一schema拒绝，不把坏参数变成服务器内部错误。
- 影响范围：预览及共用merge/codec的嵌套字段；非游戏规则问题、不泛化安全攻击。单HP后缀与坏base组合还会得到不同ValueError，属于同一缺少统一形状校验根因。
- 证据：`probe.py` 实际运行；`probe_output.json#I07_preview_invalid_base`。

## T02-I08｜确认缺陷｜P1｜奉献减耗别名错字使随机初始化崩溃

- 主责协同：T02别名/初始化主责；T10奉献消费者协同
- 规则依据/原文行号：data/部分规则详解/奉献.md:1-2；nrc_core/engine/handlers_field.py DEVOTION_TYPES；builder初始化契约
- 代码位置：nrc_platform/builder.py:30-36,245-257,285-295
- 最小输入步骤：own.devotion指定power_bonus=5、random_draws=1，seed=2，完整双方正式build；seed0..7保留全部输出。
- 预期与实际：应获得五种中的一种合法奉献。实际随机到假寐后规范化仍是假寐，RANDOM_DEVOTION_CAPS[假寐]抛KeyError。别名和LEGACY_DEVOTION_KEYS使用假寥，正式handler使用假寐。seed1/3/4抽飞断则可成功但超过上限，该独立问题归T10-I01。
- 影响范围：随机奉献初始化抽到减耗时；已知canonical cost_reduce输入也被转换成假寥，可能不能被真实假寐消费者读取。前者已实际证实，后者消费者影响需要T10协同。
- 证据：`probe.py` 实际运行；`probe_output.json#I08_devotion_alias`。

## 跨任务接口证据（不重复主问题）

- T06-I15：目录5个前缀蓄力技能均charge=False；升龙咆哮首回合能量10→7、对方HP1000→820，charging_skill_idx=-1；原文要求先蓄力1回合。证据X01_charge_catalog/X01_charge_turn。
- T10-I01：指定power5且random_draws1，seed1/3/4仍抽power并合成6；指定9+已知随机5合成14，未统一封顶/满池排除。证据I08_devotion_alias/X02_devotion_over_cap。
- T03-I03：build输入100层物攻加成保留atk_up=10而非99层9.9。证据I05_over_cap；有效属性又被模型40层限制，属于T03两处根因，不重复报。
- T05-I03：目录首领记录含types，但builder只注入boss_form名，运行时首领化不更新types，主根因在T05；远古血脉字段和映射权威性保留Q05。
- T05-I09：builder将首发entry_count至少置1，但不执行ON_ENTER，runtime也未初始调用；不因entry_count存在就认为入场效果已落实。
- T11-I01：direct builder对空effects特性明确拒绝，P01已实际验证；上层_Catalog抹掉名称绕过校验归T11，不重复。
