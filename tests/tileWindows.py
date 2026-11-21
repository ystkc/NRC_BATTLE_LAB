import ctypes
from ctypes import wintypes


user32 = ctypes.WinDLL("user32")

KEYWORD = "360极速浏览器X"
SPI_GETWORKAREA = 0x0030
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

# 与 Win32 回调签名一致：BOOL CALLBACK (HWND, LPARAM)
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def tile_windows() -> int:
    """枚举顶层窗口并分屏，返回扫描到的窗口总数。"""
    total = 0
    slot = 0  # 0 表示下一个匹配窗口占左半，否则占右半

    def callback(hwnd, _lparam):
        nonlocal total, slot
        total += 1

        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, len(title))
        if KEYWORD not in title.value:
            return True

        work = wintypes.RECT()
        user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(work), 0)
        half = (work.right - work.left) // 2
        # 第一个窗口占左半，之后的窗口占右半（宽度取剩余部分）
        x = work.left if slot == 0 else work.left + half
        width = half if slot == 0 else work.right - work.left - half
        if slot == 0:
            slot = 1

        user32.SetWindowPos(hwnd, 0, x, work.top, width,
                            work.bottom - work.top, SWP_NOACTIVATE | SWP_SHOWWINDOW)
        return True

    # 回调对象必须保持引用，否则会被垃圾回收导致崩溃
    cb = EnumWindowsProc(callback)
    user32.EnumWindows(cb, 0)
    return total
    
def main():
    total = tile_windows()
    print(f"枚举结束，扫描窗口数：{total}")

if __name__ == "__main__":
    main()