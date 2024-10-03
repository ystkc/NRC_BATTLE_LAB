#define NOMINMAX
#include <windows.h>
#include <gdiplus.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr std::uint32_t kRequestMagic = 0x3152434f;
constexpr std::uint32_t kResponseMagic = 0x3153434f;
constexpr std::uint16_t kProtocolVersion = 1;
constexpr std::uint16_t kFormatBgra32 = 1;
constexpr std::uint32_t kStatusOk = 0;
constexpr std::size_t kMaxResponseBytes = 64ull * 1024ull * 1024ull;

#pragma pack(push, 1)
struct RequestHeader {
    std::uint32_t magic;
    std::uint16_t version;
    std::uint16_t format;
    std::uint32_t width;
    std::uint32_t height;
    std::uint32_t stride;
    std::uint32_t payloadBytes;
    std::uint64_t requestId;
};

struct ResponseHeader {
    std::uint32_t magic;
    std::uint16_t version;
    std::uint16_t reserved;
    std::uint32_t status;
    std::uint32_t width;
    std::uint32_t height;
    std::uint32_t jsonBytes;
    std::uint64_t requestId;
};
#pragma pack(pop)

static_assert(sizeof(RequestHeader) == 32);
static_assert(sizeof(ResponseHeader) == 32);

std::wstring utf8ToWide(const std::string& input) {
    if (input.empty()) return {};
    const int length = MultiByteToWideChar(
        CP_UTF8, MB_ERR_INVALID_CHARS, input.data(), static_cast<int>(input.size()), nullptr, 0);
    if (length <= 0) throw std::runtime_error("path is not valid UTF-8");
    std::wstring result(length, L'\0');
    if (MultiByteToWideChar(
            CP_UTF8, MB_ERR_INVALID_CHARS, input.data(), static_cast<int>(input.size()),
            result.data(), length) <= 0) {
        throw std::runtime_error("UTF-8 path conversion failed");
    }
    return result;
}

struct Options {
    std::filesystem::path input;
    std::wstring pipeName = L"\\\\.\\pipe\\pixpin-ocr";
    int cropX = 0;
    int cropY = 0;
    int cropWidth = 0;
    int cropHeight = 0;
    std::uint64_t requestId = 1;
    int repeat = 1;
};

Options parseOptions(int argc, char** argv) {
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        auto requireValue = [&](const char* name) -> std::string {
            if (index + 1 >= argc) throw std::runtime_error(std::string(name) + " requires a value");
            return argv[++index];
        };
        if (argument == "--input") {
            options.input = std::filesystem::path(utf8ToWide(requireValue("--input")));
        } else if (argument == "--pipe-name") {
            options.pipeName = utf8ToWide(requireValue("--pipe-name"));
        } else if (argument == "--crop") {
            options.cropX = std::stoi(requireValue("--crop"));
            if (index + 3 >= argc) throw std::runtime_error("--crop requires x y width height");
            options.cropY = std::stoi(argv[++index]);
            options.cropWidth = std::stoi(argv[++index]);
            options.cropHeight = std::stoi(argv[++index]);
        } else if (argument == "--request-id") {
            options.requestId = std::stoull(requireValue("--request-id"));
        } else if (argument == "--repeat") {
            options.repeat = std::stoi(requireValue("--repeat"));
        } else if (argument == "--help" || argument == "-h") {
            std::cout << "Usage: pixpin_ocr_example_client.exe --input IMAGE [options]\n"
                         "  --pipe-name NAME       default: \\\\.\\pipe\\pixpin-ocr\n"
                         "  --crop X Y W H         crop before sending\n"
                         "  --request-id N         first request id, default: 1\n"
                         "  --repeat N             send the same frame N times on one connection\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + argument);
        }
    }
    if (options.input.empty()) throw std::runtime_error("--input is required");
    if (options.repeat <= 0) throw std::runtime_error("--repeat must be positive");
    const bool anyCrop = options.cropX != 0 || options.cropY != 0 || options.cropWidth != 0 || options.cropHeight != 0;
    if (anyCrop && (options.cropX < 0 || options.cropY < 0 || options.cropWidth <= 0 || options.cropHeight <= 0)) {
        throw std::runtime_error("--crop requires non-negative x/y and positive width/height");
    }
    return options;
}

struct GdiPlusSession {
    ULONG_PTR token = 0;

    GdiPlusSession() {
        Gdiplus::GdiplusStartupInput input;
        const auto status = Gdiplus::GdiplusStartup(&token, &input, nullptr);
        if (status != Gdiplus::Ok) throw std::runtime_error("GDI+ startup failed");
    }

    ~GdiPlusSession() {
        if (token != 0) Gdiplus::GdiplusShutdown(token);
    }
};

struct Frame {
    std::uint32_t width = 0;
    std::uint32_t height = 0;
    std::vector<std::uint8_t> pixels;
};

Frame cropFrame(const Frame& source, int x, int y, int width, int height) {
    if (x < 0 || y < 0 || width <= 0 || height <= 0 ||
        x + width > static_cast<int>(source.width) ||
        y + height > static_cast<int>(source.height)) {
        throw std::runtime_error("crop rectangle is outside the input image");
    }

    Frame result;
    result.width = static_cast<std::uint32_t>(width);
    result.height = static_cast<std::uint32_t>(height);
    result.pixels.resize(static_cast<std::size_t>(width) * height * 4);
    const auto sourceStride = static_cast<std::size_t>(source.width) * 4;
    const auto resultStride = static_cast<std::size_t>(width) * 4;
    for (int row = 0; row < height; ++row) {
        const auto* sourceRow = source.pixels.data() +
            static_cast<std::size_t>(y + row) * sourceStride + static_cast<std::size_t>(x) * 4;
        auto* resultRow = result.pixels.data() + static_cast<std::size_t>(row) * resultStride;
        std::memcpy(resultRow, sourceRow, resultStride);
    }
    return result;
}

Frame loadFrame(const std::filesystem::path& path, const Options& options) {
    Gdiplus::Bitmap bitmap(path.c_str(), FALSE);
    if (bitmap.GetLastStatus() != Gdiplus::Ok) throw std::runtime_error("GDI+ could not open input image");
    const auto width = static_cast<int>(bitmap.GetWidth());
    const auto height = static_cast<int>(bitmap.GetHeight());
    if (width <= 0 || height <= 0) throw std::runtime_error("input image has invalid dimensions");

    Frame frame;
    frame.width = static_cast<std::uint32_t>(width);
    frame.height = static_cast<std::uint32_t>(height);
    frame.pixels.resize(static_cast<std::size_t>(width) * height * 4);

    Gdiplus::Rect rectangle(0, 0, width, height);
    Gdiplus::BitmapData data{};
    auto status = bitmap.LockBits(
        &rectangle, Gdiplus::ImageLockModeRead, PixelFormat32bppARGB, &data);
    if (status != Gdiplus::Ok) throw std::runtime_error("GDI+ could not lock input pixels");

    const auto sourceStride = static_cast<std::size_t>(std::abs(data.Stride));
    const auto destinationStride = static_cast<std::size_t>(width) * 4;
    for (int row = 0; row < height; ++row) {
        const auto sourceRow = data.Stride >= 0
            ? static_cast<const std::uint8_t*>(data.Scan0) + static_cast<std::size_t>(row) * sourceStride
            : static_cast<const std::uint8_t*>(data.Scan0) + static_cast<std::size_t>(height - 1 - row) * sourceStride;
        std::memcpy(frame.pixels.data() + static_cast<std::size_t>(row) * destinationStride,
                    sourceRow, destinationStride);
    }
    bitmap.UnlockBits(&data);

    const bool anyCrop = options.cropX != 0 || options.cropY != 0 ||
                         options.cropWidth != 0 || options.cropHeight != 0;
    return anyCrop ? cropFrame(frame, options.cropX, options.cropY,
                               options.cropWidth, options.cropHeight) : std::move(frame);
}

bool writeExact(HANDLE pipe, const void* source, std::size_t bytes) {
    const auto* cursor = static_cast<const std::uint8_t*>(source);
    while (bytes > 0) {
        DWORD written = 0;
        const DWORD chunk = static_cast<DWORD>(std::min<std::size_t>(bytes, 1u << 20));
        if (!WriteFile(pipe, cursor, chunk, &written, nullptr) || written == 0) return false;
        cursor += written;
        bytes -= written;
    }
    return true;
}

bool readExact(HANDLE pipe, void* destination, std::size_t bytes) {
    auto* cursor = static_cast<std::uint8_t*>(destination);
    while (bytes > 0) {
        DWORD read = 0;
        const DWORD chunk = static_cast<DWORD>(std::min<std::size_t>(bytes, 1u << 20));
        if (!ReadFile(pipe, cursor, chunk, &read, nullptr) || read == 0) return false;
        cursor += read;
        bytes -= read;
    }
    return true;
}

HANDLE connectPipe(const std::wstring& pipeName) {
    for (;;) {
        const auto pipe = CreateFileW(pipeName.c_str(), GENERIC_READ | GENERIC_WRITE, 0,
                                       nullptr, OPEN_EXISTING, 0, nullptr);
        if (pipe != INVALID_HANDLE_VALUE) {
            DWORD mode = PIPE_READMODE_BYTE;
            SetNamedPipeHandleState(pipe, &mode, nullptr, nullptr);
            return pipe;
        }
        const auto error = GetLastError();
        if (error != ERROR_PIPE_BUSY) {
            throw std::runtime_error("CreateFileW named pipe failed: " + std::to_string(error));
        }
        if (!WaitNamedPipeW(pipeName.c_str(), 5000)) {
            throw std::runtime_error("WaitNamedPipeW timed out");
        }
    }
}

std::string receiveResponse(HANDLE pipe, std::uint64_t expectedRequestId) {
    ResponseHeader header{};
    if (!readExact(pipe, &header, sizeof(header))) throw std::runtime_error("failed to read response header");
    if (header.magic != kResponseMagic || header.version != kProtocolVersion) {
        throw std::runtime_error("invalid response header");
    }
    if (header.requestId != expectedRequestId) throw std::runtime_error("response requestId mismatch");
    if (header.jsonBytes > kMaxResponseBytes) throw std::runtime_error("response JSON is too large");
    std::string json(header.jsonBytes, '\0');
    if (!json.empty() && !readExact(pipe, json.data(), json.size())) {
        throw std::runtime_error("failed to read response JSON");
    }
    std::cerr << "status=" << header.status << " image=" << header.width << "x" << header.height
              << " requestId=" << header.requestId << "\n";
    return json;
}

int run(const Options& options) {
    if (!std::filesystem::is_regular_file(options.input)) {
        throw std::runtime_error("input image does not exist: " + options.input.string());
    }
    GdiPlusSession gdiPlus;
    const auto frame = loadFrame(options.input, options);
    const auto pipe = connectPipe(options.pipeName);
    if (pipe == INVALID_HANDLE_VALUE) throw std::runtime_error("invalid named pipe handle");

    int result = 0;
    for (int index = 0; index < options.repeat; ++index) {
        const auto requestId = options.requestId + static_cast<std::uint64_t>(index);
        RequestHeader header{};
        header.magic = kRequestMagic;
        header.version = kProtocolVersion;
        header.format = kFormatBgra32;
        header.width = frame.width;
        header.height = frame.height;
        header.stride = frame.width * 4;
        header.payloadBytes = static_cast<std::uint32_t>(frame.pixels.size());
        header.requestId = requestId;

        if (!writeExact(pipe, &header, sizeof(header)) ||
            !writeExact(pipe, frame.pixels.data(), frame.pixels.size())) {
            CloseHandle(pipe);
            throw std::runtime_error("failed to write request");
        }
        const auto json = receiveResponse(pipe, requestId);
        std::cout << json;
        if (index + 1 < options.repeat) std::cout << "\n";
        if (header.requestId == requestId && json.find("\"ok\":true") == std::string::npos) result = 2;
    }
    CloseHandle(pipe);
    return result;
}

} // namespace

int main(int argc, char** argv) {
    try {
        return run(parseOptions(argc, argv));
    } catch (const std::exception& error) {
        std::cerr << "pixpin_ocr_example_client: " << error.what() << '\n';
        return 1;
    }
}
