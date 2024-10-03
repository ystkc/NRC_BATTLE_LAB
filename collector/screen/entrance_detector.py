"""Locate entrance UI elements from pixels, without evaluation annotations."""

from __future__ import annotations

import cv2
import numpy as np

from .region_geometry import Region


class EntranceRegionDetector:
    """Color/shape segmentation with anchors measured independently per frame."""

    def __init__(self, align_card_width: bool = True, border_padding: bool = True):
        self.align_card_width = align_card_width
        self.border_padding = border_padding

    @staticmethod
    def _odd_size(value: float) -> int:
        size = max(1, round(value))
        return size if size % 2 else size + 1

    @staticmethod
    def _contours(mask: np.ndarray) -> list[np.ndarray]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours

    @staticmethod
    def _region(name: str, box: tuple[int, int, int, int], shape: tuple[int, ...], padding: int = 0) -> Region:
        height, width = shape[:2]
        x, y, box_width, box_height = box
        left, top = max(0, x - padding), max(0, y - padding)
        right, bottom = min(width, x + box_width + padding), min(height, y + box_height + padding)
        return Region(name, int(left), int(top), int(right - left), int(bottom - top))

    def _health_stacks(self, hsv: np.ndarray) -> list[list[tuple[int, int, int, int]]]:
        height, width = hsv.shape[:2]
        unit = min(height, width)
        mask = cv2.inRange(hsv, (25, 80, 70), (80, 255, 255))
        kernel = np.ones((self._odd_size(unit * 0.003), self._odd_size(unit * 0.005)), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        candidates = []
        for contour in self._contours(mask):
            x, y, box_width, box_height = cv2.boundingRect(contour)
            aspect = box_width / box_height
            fill = cv2.contourArea(contour) / (box_width * box_height)
            if 4.5 < aspect < 12 and fill > 0.65 and width * 0.025 < box_width < width * 0.15:
                candidates.append((x, y, box_width, box_height))
        stacks = []
        remaining = list(candidates)
        while remaining:
            seed = remaining.pop(0)
            group = [seed]
            for candidate in remaining[:]:
                aligned = abs(candidate[0] - seed[0]) < seed[2] * 0.25
                similar = abs(candidate[2] - seed[2]) < seed[2] * 0.25
                if aligned and similar:
                    group.append(candidate)
                    remaining.remove(candidate)
            if len(group) >= 3:
                stacks.append(sorted(group, key=lambda box: box[1]))
        return sorted(stacks, key=lambda stack: stack[0][0])

    def _card_body(self, panel_mask: np.ndarray, anchor: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
        height, width = panel_mask.shape[:2]
        x, y, bar_width, bar_height = anchor
        left, right = max(0, x - round(bar_width * 1.5)), min(width, x + round(bar_width * 1.8))
        top, bottom = max(0, y - bar_height * 4), min(height, y + bar_height * 2)
        crop = panel_mask[top:bottom, left:right]
        size = self._odd_size(bar_height * 0.15)
        crop = cv2.morphologyEx(crop, cv2.MORPH_CLOSE, np.ones((size, size), np.uint8))
        candidates = []
        for contour in self._contours(crop):
            local_x, local_y, box_width, box_height = cv2.boundingRect(contour)
            covers_bar = (
                local_x + left <= x and local_y + top <= y
                and local_x + left + box_width >= x + bar_width - 3
                and local_y + top + box_height >= y + bar_height - 3
            )
            if covers_bar:
                candidates.append(contour)
        if not candidates:
            return None
        contour = max(candidates, key=cv2.contourArea)
        filled = np.zeros_like(crop)
        cv2.drawContours(filled, [contour], -1, 255, cv2.FILLED)
        row_widths = np.count_nonzero(filled, axis=1)
        body_rows = np.flatnonzero(row_widths >= row_widths.max() * 0.55)
        if not body_rows.size:
            return None
        body_top, body_bottom = int(body_rows[0]), int(body_rows[-1]) + 1
        occupied = np.argwhere(filled[body_top:body_bottom])
        body_left, body_right = int(occupied[:, 1].min()), int(occupied[:, 1].max()) + 1
        box = (left + body_left, top + body_top, body_right - body_left, body_bottom - body_top)
        return box if 2.5 < box[2] / box[3] < 6 else None

    def _badge(self, gray: np.ndarray, body: tuple[int, int, int, int], name: str) -> Region | None:
        height, width = gray.shape
        x, y, _, body_height = body
        left, right = max(0, x - round(body_height * 0.4)), min(width, x + round(body_height * 0.7))
        top, bottom = max(0, y - round(body_height * 0.6)), min(height, y + round(body_height * 0.4))
        circles = cv2.HoughCircles(
            gray[top:bottom, left:right], cv2.HOUGH_GRADIENT, 1, max(3, body_height * 0.3),
            param1=100, param2=12, minRadius=max(3, round(body_height * 0.12)),
            maxRadius=max(5, round(body_height * 0.25)),
        )
        if circles is None:
            return None
        center_x, center_y, radius = min(
            circles[0],
            key=lambda circle: abs(circle[0] + left - x - body_height * 0.18) + abs(circle[1] + top - y),
        )
        center_x, center_y = float(center_x) + left, float(center_y) + top
        radius = float(radius) + (round(float(radius) * 0.08) if self.border_padding else 0)
        box_left, box_top = int(np.floor(center_x - radius)), int(np.floor(center_y - radius))
        box_right, box_bottom = int(np.ceil(center_x + radius)), int(np.ceil(center_y + radius))
        return self._region(name, (box_left, box_top, box_right - box_left, box_bottom - box_top), gray.shape)

    def _banners(self, dark: np.ndarray, bar_width: float | None) -> list[Region]:
        height, width = dark.shape
        unit = min(height, width)
        kernel = np.ones((self._odd_size(unit * 0.007), self._odd_size(unit * 0.02)), np.uint8)
        opened = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel)
        result = []
        for contour in self._contours(opened):
            x, y, box_width, box_height = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            aspect = box_width / box_height
            minimum_width = bar_width * 3 if bar_width else width * 0.18
            if (
                box_width > minimum_width and box_height < height * 0.2
                and 3 < aspect < 15 and area > height * width * 0.006
                and area / (box_width * box_height) > 0.55
            ):
                padding = round(box_height * 0.04) if self.border_padding and aspect > 5 else 0
                result.append(self._region("dark_banner", (x, y, box_width, box_height), dark.shape, padding))
        return sorted(result, key=lambda region: region.x)

    def _buttons(self, gold: np.ndarray, cards: list[Region]) -> list[Region]:
        height, width = gold.shape
        size = self._odd_size(min(height, width) * 0.007)
        closed = cv2.morphologyEx(gold, cv2.MORPH_CLOSE, np.ones((size, size), np.uint8))
        result = []
        for contour in self._contours(closed):
            box = cv2.boundingRect(contour)
            x, y, box_width, box_height = box
            area = cv2.contourArea(contour)
            if not (
                2.5 < box_width / box_height < 6
                and height * width * 0.002 < area < height * width * 0.02
                and area / (box_width * box_height) > 0.65
            ):
                continue
            belongs_to_card = any(
                card.x <= x + box_width / 2 < card.right
                and card.y <= y + box_height / 2 < card.bottom
                for card in cards
            )
            if not belongs_to_card:
                padding = round(box_height * 0.05) if self.border_padding else 0
                result.append(self._region("gold_button", box, gold.shape, padding))
        return result

    def _art_headers(self, dark: np.ndarray, cards: list[Region]) -> list[Region]:
        height, width = dark.shape
        padded = cv2.copyMakeBorder(dark, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=255)
        contours, hierarchy = cv2.findContours(padded, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        result = []
        if hierarchy is None:
            return result
        for index, contour in enumerate(contours):
            if hierarchy[0][index][3] < 0:
                continue
            x, y, box_width, box_height = cv2.boundingRect(contour)
            x, y = x - 1, y - 1
            if not (
                box_width > width * 0.2 and box_height < height * 0.2
                and box_width / box_height > 4.5
                and cv2.contourArea(contour) > height * width * 0.008
            ):
                continue
            above_team = any(
                x < card.x + card.w / 2 < x + box_width and y + box_height < card.y
                for card in cards
            )
            if above_team:
                result.append(self._region("team_art_header", (x, y, box_width, box_height), dark.shape))
        return result

    def _emblems(self, hsv: np.ndarray) -> list[Region]:
        height, width = hsv.shape[:2]
        size = self._odd_size(min(height, width) * 0.005)
        bright = cv2.inRange(hsv, (0, 0, 170), (179, 85, 255))
        bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((size, size), np.uint8))
        result = []
        for contour in self._contours(bright):
            x, y, box_width, box_height = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            if not (
                0.75 < box_width / box_height < 1.35 and area / (box_width * box_height) > 0.55
                and box_width > width * 0.08 and box_height > height * 0.08
                and area > height * width * 0.006
            ):
                continue
            left, top = max(0, x - box_width // 3), max(0, y - box_height // 3)
            right = min(width, x + box_width + box_width // 3)
            bottom = min(height, y + box_height + box_height // 3)
            mask = cv2.inRange(hsv[top:bottom, left:right], (0, 0, 15), (179, 80, 255))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((size, size), np.uint8))
            opening_size = self._odd_size(min(box_width, box_height) * 0.1)
            opening = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (opening_size, opening_size))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, opening)
            components = self._contours(mask)
            if not components:
                continue
            component = max(components, key=cv2.contourArea)
            local_x, local_y, component_width, component_height = cv2.boundingRect(component)
            if 0.7 < component_width / component_height < 1.4:
                result.append(self._region(
                    "central_emblem", (left + local_x, top + local_y, component_width, component_height), hsv.shape,
                ))
        return result

    def detect(self, image: np.ndarray) -> list[Region]:
        if image is None or image.ndim != 3 or image.shape[2] != 3 or image.size == 0:
            raise ValueError("Expected a non-empty BGR image")
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        dark = cv2.inRange(image, (10, 10, 10), (65, 65, 65))
        gold = cv2.inRange(hsv, (12, 80, 160), (40, 255, 255))
        panel_mask = cv2.bitwise_or(dark, gold)
        stacks = self._health_stacks(hsv)
        cards, badges = [], []
        bar_widths = []
        for stack_index, stack in enumerate(stacks, start=1):
            bodies = []
            for anchor in stack:
                body = self._card_body(panel_mask, anchor)
                if body is not None:
                    bodies.append((body, anchor))
                    bar_widths.append(anchor[2])
            if not bodies:
                continue
            common_width = max(body[2] for body, _ in bodies)
            padding = round(float(np.median([anchor[3] for _, anchor in bodies])) * 0.18) if self.border_padding else 0
            for slot_index, (body, _) in enumerate(bodies, start=1):
                name = f"team_{stack_index}_slot_{slot_index}"
                card_width = common_width if self.align_card_width else body[2]
                cards.append(self._region(name + "_card", (body[0], body[1], card_width, body[3]), image.shape, padding))
                badge = self._badge(gray, body, name + "_badge")
                if badge is not None:
                    badges.append(badge)
        median_bar_width = float(np.median(bar_widths)) if bar_widths else None
        regions = cards + badges + self._banners(dark, median_bar_width)
        regions += self._buttons(gold, cards)
        regions += self._art_headers(dark, cards)
        regions += self._emblems(hsv)
        return sorted(regions, key=lambda region: (region.y, region.x, region.name))
