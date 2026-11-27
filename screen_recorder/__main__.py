"""在本机启动屏幕 OCR Web 服务。"""

import argparse

import uvicorn


def main() -> None:
    """解析端口并启动本机服务。"""
    parser = argparse.ArgumentParser(description="屏幕 OCR Web 界面")
    parser.add_argument("--port", type=int, default=8768, help="本机 Web 服务端口")
    args = parser.parse_args()
    uvicorn.run("screen_recorder.server:app", host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
