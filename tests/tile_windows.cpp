#include <psapi.h>
  #include <iostream>
  #include <string>

  void Print(const std::wstring& s)
  {
      DWORD written = 0;
      WriteConsoleW(GetStdHandle(STD_OUTPUT_HANDLE), s.c_str(), (DWORD)s.size(), &written, nullptr);
  }

  int slot = 0;

  BOOL CALLBACK FindWindowByName(HWND hwnd, LPARAM lParam)
  {
      int* count = (int*)lParam;
      (*count)++;

  wchar_t title[512] = {0};
  GetWindowTextW(hwnd, title, _countof(title));

  if (wcsstr(title, L"360极速浏览器X") == nullptr)
      return TRUE;

  DWORD pid = 0;
  GetWindowThreadProcessId(hwnd, &pid);

  RECT work{};
  SystemParametersInfoW(SPI_GETWORKAREA, 0, &work, 0);
  const int half = (work.right - work.left) / 2;
  const int x = slot ==
  const int width = slot == 0 ? half : work.right - work.left - half;
  if (slot == 0) slot = 1;
  if (!SetWindowPos(hwnd, HWND_TOP, x, work.top, width, work.bottom - work.top,
                    SWP_NOACTIVATE | SWP_SHOWWINDOW)) return 1;
  return TRUE;
  }

  int main()
  {
      SetConsoleOutputCP(CP_UTF8);
      int total = 0;

  Print(L"开始枚举窗口...\n");
  EnumWindows(FindWindowByName, (LPARAM)&total);

  Print(L"枚举结束，扫描窗口数：" + std::to_wstring(total) + L"\n");
  if (total == 0)
      Print(L"（没找到任何含 360 的窗口，或 360 没开）\n");

  Print(L"回车退出\n");
  getchar();
  return 0;
  }