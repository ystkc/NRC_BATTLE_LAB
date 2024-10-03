"""Image-region geometry shared by detection and evaluation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    name: str
    x: int
    y: int
    w: int
    h: int
    weight: int = 0

    @property
    def area(self) -> int:
        return self.w * self.h

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    def as_xywh(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.w, self.h
