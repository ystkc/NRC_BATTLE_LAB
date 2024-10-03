#define NOMINMAX
#include <windows.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <future>
#include <iostream>
#include <memory>
#include <mutex>
#include <queue>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

constexpr int kOcrModeFull = 2;
constexpr int kQtDirectConnection = 1;
constexpr std::size_t kQImageStorage = 256;
constexpr std::size_t kQCoreApplicationStorage = 1024;
constexpr std::size_t kPixOcrParamsStorage = 0x100;
constexpr std::size_t kPixOcrObjectStorage = 4096;
constexpr std::uint32_t kRequestMagic = 0x3152434f;
constexpr std::uint32_t kResponseMagic = 0x3153434f;
constexpr std::uint16_t kProtocolVersion = 1;
constexpr std::uint16_t kFormatBgra32 = 1;
constexpr std::uint32_t kStatusOk = 0;
constexpr std::uint32_t kStatusBadRequest = 1;
constexpr std::uint32_t kStatusBusy = 2;
constexpr std::uint32_t kStatusOcrError = 3;
constexpr std::uint32_t kStatusTimeout = 4;
constexpr std::uint32_t kStatusServerError = 5;
constexpr std::size_t kDefaultMaxFrameBytes = 64ull * 1024ull * 1024ull;
constexpr std::size_t kDefaultQueueDepth = 32;

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

struct alignas(16) Storage {
    std::vector<std::uint8_t> bytes;

    explicit Storage(std::size_t size) : bytes(size, 0) {}

    void* data() { return bytes.data(); }
    const void* data() const { return bytes.data(); }
};

template <typename Function>
Function resolve(HMODULE module, const char* name) {
    auto address = GetProcAddress(module, name);
    if (address == nullptr) {
        throw std::runtime_error(std::string("Missing export: ") + name);
    }
    return reinterpret_cast<Function>(address);
}

struct Libraries {
    HMODULE core = nullptr;
    HMODULE gui = nullptr;
    HMODULE modelRunner = nullptr;
    HMODULE ocr = nullptr;

    ~Libraries() {
        unload();
    }

    void unload() noexcept {
        if (ocr != nullptr) FreeLibrary(ocr);
        if (modelRunner != nullptr) FreeLibrary(modelRunner);
        if (gui != nullptr) FreeLibrary(gui);
        if (core != nullptr) FreeLibrary(core);
        ocr = nullptr;
        modelRunner = nullptr;
        gui = nullptr;
        core = nullptr;
    }

    void load(const std::filesystem::path& directory) {
        unload();
        SetDllDirectoryW(directory.c_str());
        HMODULE loadedCore = nullptr;
        HMODULE loadedGui = nullptr;
        HMODULE loadedModelRunner = nullptr;
        HMODULE loadedOcr = nullptr;
        try {
            loadedCore = loadOne(directory / L"Qt5Core.dll");
            loadedGui = loadOne(directory / L"Qt5Gui.dll");
            loadedModelRunner = loadOne(directory / L"PixModelRunner.dll");
            loadedOcr = loadOne(directory / L"PixOCR2.dll");
        } catch (...) {
            if (loadedOcr != nullptr) FreeLibrary(loadedOcr);
            if (loadedModelRunner != nullptr) FreeLibrary(loadedModelRunner);
            if (loadedGui != nullptr) FreeLibrary(loadedGui);
            if (loadedCore != nullptr) FreeLibrary(loadedCore);
            throw;
        }
        core = loadedCore;
        gui = loadedGui;
        modelRunner = loadedModelRunner;
        ocr = loadedOcr;
    }

private:
    static HMODULE loadOne(const std::filesystem::path& path) {
        auto module = LoadLibraryW(path.c_str());
        if (module == nullptr) {
            throw std::runtime_error("Unable to load " + path.string() +
                                     ", Win32 error=" + std::to_string(GetLastError()));
        }
        return module;
    }
};

using QCoreApplicationCtor = void (*)(void*, int*, char**, int);
using QCoreApplicationDtor = void (*)(void*);
using QCoreApplicationExec = int (*)();
using QCoreApplicationQuit = void (*)();
using QImageRawCtor = void (*)(void*, const unsigned char*, int, int, int, int, void (*)(void*), void*);
using QImageDtor = void (*)(void*);
using QImageIsNull = bool (*)(const void*);
using QStringDefaultCtor = void (*)(void*);
using QStringCstrCtor = void (*)(void*, const char*);
using QStringDtor = void (*)(void*);
using PixOcrObjectCtor = void (*)(void*, const void*, const void*, int, void*);
using PixOcrObjectDtor = void (*)(void*);
using PixOcrObjectHasError = bool (*)(const void*);
using PixOcrObjectGetLayoutResult = const void* (*)(const void*);
using PixOcrObjectShutdown = void (*)();
using QObjectConnect = void (*)(void*, const void*, const char*, const void*, const char*, int);
using TextBlockListToJson = void (*)(const void*, void*);
using QJsonDocumentDtor = void (*)(void*);
using QJsonDocumentToJson = void (*)(const void*, void*);
using QByteArrayDtor = void (*)(void*);
using QByteArrayConstData = const char* (*)(const void*);
using QByteArraySize = int (*)(const void*);

struct Api {
    QCoreApplicationCtor coreApplicationCtor;
    QCoreApplicationDtor coreApplicationDtor;
    QCoreApplicationExec coreApplicationExec;
    QCoreApplicationQuit coreApplicationQuit;
    QImageRawCtor qImageRawCtor;
    QImageDtor qImageDtor;
    QImageIsNull qImageIsNull;
    QStringDefaultCtor qStringDefaultCtor;
    QStringCstrCtor qStringCstrCtor;
    QStringDtor qStringDtor;
    PixOcrObjectCtor pixOcrObjectCtor;
    PixOcrObjectDtor pixOcrObjectDtor;
    PixOcrObjectHasError pixOcrObjectHasError;
    PixOcrObjectGetLayoutResult pixOcrObjectGetLayoutResult;
    PixOcrObjectShutdown pixOcrObjectShutdown;
    QObjectConnect qObjectConnect;
    TextBlockListToJson textBlockListToJson;
    QJsonDocumentDtor qJsonDocumentDtor;
    QJsonDocumentToJson qJsonDocumentToJson;
    QByteArrayDtor qByteArrayDtor;
    QByteArrayConstData qByteArrayConstData;
    QByteArraySize qByteArraySize;
};

Api resolveApi(const Libraries& libraries) {
    Api api{};
    api.coreApplicationCtor = resolve<QCoreApplicationCtor>(libraries.core, "??0QCoreApplication@@QEAA@AEAHPEAPEADH@Z");
    api.coreApplicationDtor = resolve<QCoreApplicationDtor>(libraries.core, "??1QCoreApplication@@UEAA@XZ");
    api.coreApplicationExec = resolve<QCoreApplicationExec>(libraries.core, "?exec@QCoreApplication@@SAHXZ");
    api.coreApplicationQuit = resolve<QCoreApplicationQuit>(libraries.core, "?quit@QCoreApplication@@SAXXZ");
    api.qImageRawCtor = resolve<QImageRawCtor>(libraries.gui, "??0QImage@@QEAA@PEBEHHHW4Format@0@P6AXPEAX@Z2@Z");
    api.qImageDtor = resolve<QImageDtor>(libraries.gui, "??1QImage@@UEAA@XZ");
    api.qImageIsNull = resolve<QImageIsNull>(libraries.gui, "?isNull@QImage@@QEBA_NXZ");
    api.qStringDefaultCtor = resolve<QStringDefaultCtor>(libraries.core, "??0QString@@QEAA@XZ");
    api.qStringCstrCtor = resolve<QStringCstrCtor>(libraries.core, "??0QString@@QEAA@PEBD@Z");
    api.qStringDtor = resolve<QStringDtor>(libraries.core, "??1QString@@QEAA@XZ");
    api.pixOcrObjectCtor = resolve<PixOcrObjectCtor>(libraries.ocr, "??0PixOcrObject@PixOcr@@QEAA@VQImage@@UPixOcrParams@1@W4OcrMode@1@PEAVQObject@@@Z");
    api.pixOcrObjectDtor = resolve<PixOcrObjectDtor>(libraries.ocr, "??1PixOcrObject@PixOcr@@UEAA@XZ");
    api.pixOcrObjectHasError = resolve<PixOcrObjectHasError>(libraries.ocr, "?hasError@PixOcrObject@PixOcr@@QEBA_NXZ");
    api.pixOcrObjectGetLayoutResult = resolve<PixOcrObjectGetLayoutResult>(libraries.ocr, "?getLayoutResult@PixOcrObject@PixOcr@@QEBAAEBVTextBlockList@2@XZ");
    api.pixOcrObjectShutdown = resolve<PixOcrObjectShutdown>(libraries.ocr, "?shutdown@PixOcrObject@PixOcr@@SAXXZ");
    api.qObjectConnect = resolve<QObjectConnect>(libraries.core, "?connect@QObject@@SA?AVConnection@QMetaObject@@PEBV1@PEBD01W4ConnectionType@Qt@@@Z");
    api.textBlockListToJson = resolve<TextBlockListToJson>(libraries.ocr, "?toJson@TextBlockList@PixOcr@@QEBA?AVQJsonDocument@@XZ");
    api.qJsonDocumentDtor = resolve<QJsonDocumentDtor>(libraries.core, "??1QJsonDocument@@QEAA@XZ");
    api.qJsonDocumentToJson = resolve<QJsonDocumentToJson>(libraries.core, "?toJson@QJsonDocument@@QEBA?AVQByteArray@@XZ");
    api.qByteArrayDtor = resolve<QByteArrayDtor>(libraries.core, "??1QByteArray@@QEAA@XZ");
    api.qByteArrayConstData = resolve<QByteArrayConstData>(libraries.core, "?constData@QByteArray@@QEBAPEBDXZ");
    api.qByteArraySize = resolve<QByteArraySize>(libraries.core, "?size@QByteArray@@QEBAHXZ");
    return api;
}

std::filesystem::path executableDirectory() {
    std::wstring buffer(32768, L'\0');
    auto length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length == 0 || length >= buffer.size()) {
        throw std::runtime_error("GetModuleFileNameW failed");
    }
    buffer.resize(length);
    return std::filesystem::path(buffer).parent_path();
}

std::filesystem::path utf8Path(const std::string& input) {
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input.data(), static_cast<int>(input.size()), nullptr, 0);
    if (length <= 0) throw std::runtime_error("Path is not valid UTF-8");
    std::wstring wide(length, L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input.data(), static_cast<int>(input.size()), wide.data(), length);
    return std::filesystem::path(wide);
}

std::wstring utf8Wide(const std::string& input) {
    return utf8Path(input).wstring();
}

std::wstring normalizePipeName(std::wstring value) {
    if (value.empty()) throw std::runtime_error("pipe name is empty");

    std::size_t leadingSlashes = 0;
    while (leadingSlashes < value.size() && value[leadingSlashes] == L'\\') {
        ++leadingSlashes;
    }
    if (leadingSlashes < 2) {
        throw std::runtime_error("pipe name must start with \\\\.\\pipe\\");
    }

    std::wstring normalized = L"\\\\";
    bool previousSlash = false;
    for (std::size_t index = leadingSlashes; index < value.size(); ++index) {
        const wchar_t character = value[index];
        if (character == L'\\') {
            if (!previousSlash) normalized.push_back(character);
            previousSlash = true;
        } else {
            normalized.push_back(character);
            previousSlash = false;
        }
    }

    if (normalized.rfind(L"\\\\.\\pipe\\", 0) != 0 || normalized.size() <= 9) {
        throw std::runtime_error("pipe name must use the form \\\\.\\pipe\\name");
    }
    return normalized;
}


std::string trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

struct Config {
    std::filesystem::path pixpinDir;
    std::filesystem::path detectionModel;
    std::filesystem::path recognitionModel;
    std::filesystem::path paragraphRecognitionModel;
    std::string language = "zh-cn";
    std::wstring pipeName = L"\\\\.\\pipe\\pixpin-ocr";
    int timeoutMs = 30000;
    std::size_t maxFrameBytes = kDefaultMaxFrameBytes;
    std::size_t queueDepth = kDefaultQueueDepth;
    std::filesystem::path configPath;
};

void applyConfigValue(Config& config, const std::string& key, const std::string& value) {
    if (key == "pixpin_dir") config.pixpinDir = utf8Path(value);
    else if (key == "detection_model") config.detectionModel = utf8Path(value);
    else if (key == "recognition_model") config.recognitionModel = utf8Path(value);
    else if (key == "language") config.language = value;
    else if (key == "pipe_name") config.pipeName = normalizePipeName(utf8Wide(value));
    else if (key == "timeout_ms") config.timeoutMs = std::stoi(value);
    else if (key == "max_frame_bytes") config.maxFrameBytes = static_cast<std::size_t>(std::stoull(value));
    else if (key == "queue_depth") config.queueDepth = static_cast<std::size_t>(std::stoull(value));
}

void setPixpinDirectory(Config& config, std::filesystem::path directory) {
    if (!directory.is_absolute()) directory = std::filesystem::absolute(directory);
    config.pixpinDir = std::move(directory);
    config.detectionModel = config.pixpinDir / L"model" / L"2478d3813bea9afacf7fee18abb09d45.bin";
    config.recognitionModel = config.pixpinDir / L"model" / L"cb6cc28d4121651b3f5bc3daecc9188e.bin";
    config.paragraphRecognitionModel = config.pixpinDir / L"model" / L"paragraph_recognition.onnx";
}

void loadIni(Config& config, const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("Unable to open config: " + path.string());
    std::string line;
    while (std::getline(input, line)) {
        if (!line.empty() && static_cast<unsigned char>(line[0]) == 0xef) line.erase(0, 3);
        auto comment = line.find_first_of("#;");
        if (comment != std::string::npos) line.resize(comment);
        auto separator = line.find('=');
        if (separator == std::string::npos) continue;
        auto key = trim(line.substr(0, separator));
        auto value = trim(line.substr(separator + 1));
        if (!key.empty() && !value.empty()) applyConfigValue(config, key, value);
    }
}

Config parseConfig(int argc, char** argv) {
    Config config;
    auto exeDir = executableDirectory();
    config.configPath = exeDir / L"pixpin-ocr.ini";
    bool explicitConfig = false;
    for (int index = 1; index + 1 < argc; ++index) {
        if (std::string(argv[index]) == "--config") {
            config.configPath = utf8Path(argv[index + 1]);
            explicitConfig = true;
        }
    }
    if (explicitConfig || std::filesystem::exists(config.configPath)) {
        if (!std::filesystem::exists(config.configPath)) {
            throw std::runtime_error("Config file does not exist: " + config.configPath.string());
        }
        loadIni(config, config.configPath);
    }

    if (const char* environment = std::getenv("PIXPIN_DIR")) {
        config.pixpinDir = utf8Path(environment);
    }
    for (int index = 1; index < argc; ++index) {
        std::string arg = argv[index];
        if (arg == "--config" && index + 1 < argc) config.configPath = utf8Path(argv[++index]);
        else if (arg == "--pixpin-dir" && index + 1 < argc) config.pixpinDir = utf8Path(argv[++index]);
        else if (arg == "--pipe-name" && index + 1 < argc) config.pipeName = normalizePipeName(utf8Wide(argv[++index]));
        else if (arg == "--timeout-ms" && index + 1 < argc) config.timeoutMs = std::stoi(argv[++index]);
        else if (arg == "--max-frame-bytes" && index + 1 < argc) config.maxFrameBytes = static_cast<std::size_t>(std::stoull(argv[++index]));
        else if (arg == "--queue-depth" && index + 1 < argc) config.queueDepth = static_cast<std::size_t>(std::stoull(argv[++index]));
        else if (arg == "--help" || arg == "-h") {
            std::cout << "Usage: pixpin_ocr_service.exe [--config FILE] [--pixpin-dir DIR] [--pipe-name NAME]\n";
            std::exit(0);
        } else if (arg.rfind("--", 0) == 0 && arg != "--server") {
            throw std::runtime_error("Unknown argument: " + arg);
        }
    }
    if (config.pixpinDir.empty()) throw std::runtime_error("PixPin directory is not configured; use --pixpin-dir or PIXPIN_DIR");
    setPixpinDirectory(config, config.pixpinDir);
    if (config.timeoutMs < 1000 || config.timeoutMs > 300000) throw std::runtime_error("timeout_ms must be between 1000 and 300000");
    if (config.maxFrameBytes < 4096 || config.maxFrameBytes > 512ull * 1024ull * 1024ull) throw std::runtime_error("max_frame_bytes is out of range");
    if (config.queueDepth == 0 || config.queueDepth > 4096) throw std::runtime_error("queue_depth is out of range");
    return config;
}

struct Request {
    std::uint64_t requestId = 0;
    std::uint32_t width = 0;
    std::uint32_t height = 0;
    std::vector<std::uint8_t> pixels;
};

struct Response {
    std::uint32_t status = kStatusServerError;
    std::uint32_t width = 0;
    std::uint32_t height = 0;
    std::uint64_t requestId = 0;
    std::string json;
};

std::string jsonEscape(const std::string& input) {
    std::string result;
    result.reserve(input.size() + 16);
    for (unsigned char character : input) {
        switch (character) {
        case '"': result += "\\\""; break;
        case '\\': result += "\\\\"; break;
        case '\n': result += "\\n"; break;
        case '\r': result += "\\r"; break;
        case '\t': result += "\\t"; break;
        default:
            if (character < 0x20) {
                char escaped[8]{};
                std::snprintf(escaped, sizeof(escaped), "\\u%04x", character);
                result += escaped;
            } else result.push_back(static_cast<char>(character));
        }
    }
    return result;
}

std::vector<std::uint8_t> rotateBgra180(const std::vector<std::uint8_t>& pixels,
                                        std::uint32_t width,
                                        std::uint32_t height) {
    const auto rowBytes = static_cast<std::size_t>(width) * 4;
    std::vector<std::uint8_t> rotated(pixels.size());
    for (std::uint32_t y = 0; y < height; ++y) {
        for (std::uint32_t x = 0; x < width; ++x) {
            const auto source = (static_cast<std::size_t>(height - 1 - y) * width + (width - 1 - x)) * 4;
            const auto destination = static_cast<std::size_t>(y) * rowBytes + static_cast<std::size_t>(x) * 4;
            std::memcpy(rotated.data() + destination, pixels.data() + source, 4);
        }
    }
    return rotated;
}

class OcrEngine {
public:
    explicit OcrEngine(const Config& config) : config_(config) {
        const auto configuredDirectory = config_.pixpinDir;
        try {
            initializeFromDirectory(configuredDirectory);
        } catch (const std::exception& primaryError) {
            const auto fallbackDirectory = executableDirectory();
            try {
                initializeFromDirectory(fallbackDirectory);
            } catch (const std::exception& fallbackError) {
                throw std::runtime_error(
                    "PixPin initialization failed under " + configuredDirectory.string() +
                    ": " + primaryError.what() + "; fallback failed under " +
                    fallbackDirectory.string() + ": " + fallbackError.what());
            }
            std::cerr << "PixPin initialization failed under " << configuredDirectory.string()
                      << "; using internal environment " << fallbackDirectory.string()
                      << ": " << primaryError.what() << '\n';
        }
        qtArgc_ = 1;
        qtArgv_[0] = applicationName_;
        qtArgv_[1] = nullptr;
        api_.coreApplicationCtor(coreApplication_.data(), &qtArgc_, qtArgv_, 0);
        applicationReady_ = true;
    }

    ~OcrEngine() {
        if (applicationReady_) {
            api_.pixOcrObjectShutdown();
            api_.coreApplicationDtor(coreApplication_.data());
        }
    }

    Response recognize(Request request) {
        auto response = recognizeOnce(request);
        if (response.status != kStatusOcrError) return response;

        Request rotated = request;
        rotated.pixels = rotateBgra180(request.pixels, request.width, request.height);
        return recognizeOnce(std::move(rotated));
    }

private:
    Response recognizeOnce(Request request) {
        Response response;
        response.requestId = request.requestId;
        response.width = request.width;
        response.height = request.height;
        Storage image(kQImageStorage);
        Storage params(kPixOcrParamsStorage);
        Storage ocrObject(kPixOcrObjectStorage);
        bool imageReady = false;
        bool objectReady = false;
        bool paramsReady = false;
        try {
            api_.qImageRawCtor(image.data(), request.pixels.data(), static_cast<int>(request.width), static_cast<int>(request.height), static_cast<int>(request.width * 4), 5, nullptr, nullptr);
            imageReady = true;
            if (api_.qImageIsNull(image.data())) throw std::runtime_error("QImage construction failed");

            auto detection = config_.detectionModel.string();
            auto recognition = config_.recognitionModel.string();
            api_.qStringCstrCtor(static_cast<std::uint8_t*>(params.data()) + 0x00, detection.c_str());
            api_.qStringCstrCtor(static_cast<std::uint8_t*>(params.data()) + 0x50, recognition.c_str());
            api_.qStringCstrCtor(static_cast<std::uint8_t*>(params.data()) + 0x60, config_.language.c_str());
            api_.qStringDefaultCtor(static_cast<std::uint8_t*>(params.data()) + 0x68);
            paramsReady = true;
            api_.pixOcrObjectCtor(ocrObject.data(), image.data(), params.data(), kOcrModeFull, nullptr);
            objectReady = true;

            Storage connection(64);
            Storage errorConnection(64);
            api_.qObjectConnect(connection.data(), ocrObject.data(), "2sigPixOcrRecFinished()", coreApplication_.data(), "1quit()", kQtDirectConnection);
            api_.qObjectConnect(errorConnection.data(), ocrObject.data(), "2sigError(PixOcrError)", coreApplication_.data(), "1quit()", kQtDirectConnection);
            std::atomic<bool> timedOut{false};
            std::mutex timeoutMutex;
            std::condition_variable timeoutCondition;
            bool finished = false;
            std::thread timeoutThread([&] {
                std::unique_lock<std::mutex> lock(timeoutMutex);
                const bool completed = timeoutCondition.wait_for(
                    lock,
                    std::chrono::milliseconds(config_.timeoutMs),
                    [&] { return finished; });
                if (!completed) {
                    timedOut.store(true, std::memory_order_release);
                    api_.coreApplicationQuit();
                }
            });
            api_.coreApplicationExec();
            {
                std::lock_guard<std::mutex> lock(timeoutMutex);
                finished = true;
            }
            timeoutCondition.notify_one();
            timeoutThread.join();

            if (timedOut.load(std::memory_order_acquire)) {
                response.status = kStatusTimeout;
                response.json = "{\"ok\":false,\"error\":\"OCR timeout\"}";
            } else if (api_.pixOcrObjectHasError(ocrObject.data())) {
                response.status = kStatusOcrError;
                response.json = "{\"ok\":false,\"error\":\"PixOCR reported an error\"}";
            } else {
                const void* layout = api_.pixOcrObjectGetLayoutResult(ocrObject.data());
                Storage jsonDocument(128);
                api_.textBlockListToJson(layout, jsonDocument.data());
                Storage byteArray(64);
                api_.qJsonDocumentToJson(jsonDocument.data(), byteArray.data());
                const auto* data = api_.qByteArrayConstData(byteArray.data());
                const auto size = api_.qByteArraySize(byteArray.data());
                std::string nativeJson;
                if (data != nullptr && size > 0) nativeJson.assign(data, data + size);
                api_.qByteArrayDtor(byteArray.data());
                api_.qJsonDocumentDtor(jsonDocument.data());
                if (nativeJson.empty()) {
                    response.status = kStatusOcrError;
                    response.json = "{\"ok\":false,\"error\":\"OCR returned empty JSON\"}";
                } else {
                    response.status = kStatusOk;
                    response.json = "{\"ok\":true,\"image\":{\"width\":" + std::to_string(request.width) + ",\"height\":" + std::to_string(request.height) + "},\"result\":" + nativeJson + "}";
                }
            }
        } catch (const std::exception& error) {
            response.status = kStatusServerError;
            response.json = "{\"ok\":false,\"error\":\"" + jsonEscape(error.what()) + "\"}";
        }
        if (objectReady) api_.pixOcrObjectDtor(ocrObject.data());
        if (paramsReady) {
            api_.qStringDtor(static_cast<std::uint8_t*>(params.data()) + 0x68);
            api_.qStringDtor(static_cast<std::uint8_t*>(params.data()) + 0x60);
            api_.qStringDtor(static_cast<std::uint8_t*>(params.data()) + 0x50);
            api_.qStringDtor(static_cast<std::uint8_t*>(params.data()) + 0x00);
        }
        if (imageReady) api_.qImageDtor(image.data());
        return response;
    }

private:
    void initializeFromDirectory(const std::filesystem::path& directory) {
        Config candidate = config_;
        setPixpinDirectory(candidate, directory);
        if (!std::filesystem::is_regular_file(candidate.pixpinDir / L"Qt5Core.dll")) {
            throw std::runtime_error("Qt5Core.dll not found under PixPin directory");
        }
        if (!std::filesystem::is_regular_file(candidate.pixpinDir / L"PixOCR2.dll")) {
            throw std::runtime_error("PixOCR2.dll not found under PixPin directory");
        }
        if (!std::filesystem::is_regular_file(candidate.detectionModel)) {
            throw std::runtime_error("Detection model not found: " + candidate.detectionModel.string());
        }
        if (!std::filesystem::is_regular_file(candidate.recognitionModel)) {
            throw std::runtime_error("Recognition model not found: " + candidate.recognitionModel.string());
        }
        if (!std::filesystem::is_regular_file(candidate.paragraphRecognitionModel)) {
            throw std::runtime_error("Paragraph recognition model not found: " + candidate.paragraphRecognitionModel.string());
        }
        libraries_.load(candidate.pixpinDir);
        const auto candidateApi = resolveApi(libraries_);
        config_ = std::move(candidate);
        api_ = candidateApi;
    }

    Config config_;
    Libraries libraries_;
    Api api_{};
    Storage coreApplication_{kQCoreApplicationStorage};
    int qtArgc_ = 0;
    char applicationName_[32] = "pixpin_ocr_service";
    char* qtArgv_[2]{};
    bool applicationReady_ = false;
};

struct Task {
    Request request;
    std::promise<Response> promise;
};

class OcrQueue {
public:
    explicit OcrQueue(std::size_t capacity) : capacity_(capacity) {}

    std::future<Response> submit(Request request) {
        auto task = std::make_shared<Task>();
        task->request = std::move(request);
        auto future = task->promise.get_future();
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (closed_) throw std::runtime_error("OCR queue is shutting down");
            if (tasks_.size() >= capacity_) throw std::runtime_error("OCR queue is full");
            tasks_.push(std::move(task));
        }
        condition_.notify_one();
        return future;
    }

    std::shared_ptr<Task> pop() {
        std::unique_lock<std::mutex> lock(mutex_);
        condition_.wait(lock, [&] { return closed_ || !tasks_.empty(); });
        if (tasks_.empty()) return {};
        auto task = tasks_.front();
        tasks_.pop();
        return task;
    }

    void close() {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            closed_ = true;
        }
        condition_.notify_all();
    }

private:
    std::size_t capacity_;
    std::mutex mutex_;
    std::condition_variable condition_;
    std::queue<std::shared_ptr<Task>> tasks_;
    bool closed_ = false;
};

class OcrWorker {
public:
    OcrWorker(const Config& config, OcrQueue& queue) : config_(config), queue_(queue), thread_(&OcrWorker::run, this) {}
    ~OcrWorker() {
        queue_.close();
        if (thread_.joinable()) thread_.join();
    }

private:
    void run() {
        try {
            OcrEngine engine(config_);
            readyPromise_.set_value();
            while (auto task = queue_.pop()) {
                try {
                    task->promise.set_value(engine.recognize(std::move(task->request)));
                } catch (const std::exception& error) {
                    Response response;
                    response.status = kStatusServerError;
                    response.requestId = task->request.requestId;
                    response.json = "{\"ok\":false,\"error\":\"" + jsonEscape(error.what()) + "\"}";
                    task->promise.set_value(std::move(response));
                }
            }
        } catch (...) {
            try { readyPromise_.set_exception(std::current_exception()); } catch (...) {}
            while (auto task = queue_.pop()) {
                Response response;
                response.status = kStatusServerError;
                response.requestId = task->request.requestId;
                response.json = "{\"ok\":false,\"error\":\"OCR engine initialization failed\"}";
                task->promise.set_value(std::move(response));
            }
        }
    }

public:
    void waitReady() { readyPromise_.get_future().get(); }

private:
    Config config_;
    OcrQueue& queue_;
    std::thread thread_;
    std::promise<void> readyPromise_;
};

bool readExact(HANDLE pipe, void* destination, std::size_t bytes) {
    auto* cursor = static_cast<std::uint8_t*>(destination);
    while (bytes > 0) {
        DWORD chunk = 0;
        const DWORD requested = static_cast<DWORD>(std::min<std::size_t>(bytes, 1u << 20));
        if (!ReadFile(pipe, cursor, requested, &chunk, nullptr) || chunk == 0) return false;
        cursor += chunk;
        bytes -= chunk;
    }
    return true;
}

bool writeExact(HANDLE pipe, const void* source, std::size_t bytes) {
    const auto* cursor = static_cast<const std::uint8_t*>(source);
    while (bytes > 0) {
        DWORD chunk = 0;
        const DWORD requested = static_cast<DWORD>(std::min<std::size_t>(bytes, 1u << 20));
        if (!WriteFile(pipe, cursor, requested, &chunk, nullptr) || chunk == 0) return false;
        cursor += chunk;
        bytes -= chunk;
    }
    return true;
}

bool validRequest(const RequestHeader& header, std::size_t maxFrameBytes) {
    if (header.magic != kRequestMagic || header.version != kProtocolVersion || header.format != kFormatBgra32) return false;
    if (header.width == 0 || header.height == 0 || header.width > 16384 || header.height > 16384) return false;
    if (header.stride < header.width * 4u || header.stride > 65536u) return false;
    const auto expected = static_cast<std::uint64_t>(header.stride) * header.height;
    return expected == header.payloadBytes && expected <= maxFrameBytes;
}

void sendResponse(HANDLE pipe, const Response& response) {
    ResponseHeader header{};
    header.magic = kResponseMagic;
    header.version = kProtocolVersion;
    header.status = response.status;
    header.width = response.width;
    header.height = response.height;
    header.jsonBytes = static_cast<std::uint32_t>(response.json.size());
    header.requestId = response.requestId;
    writeExact(pipe, &header, sizeof(header));
    if (!response.json.empty()) writeExact(pipe, response.json.data(), response.json.size());
}

void handleClient(HANDLE pipe, OcrQueue& queue, std::size_t maxFrameBytes) {
    while (true) {
        RequestHeader header{};
        if (!readExact(pipe, &header, sizeof(header))) break;
        if (!validRequest(header, maxFrameBytes)) {
            Response response;
            response.status = kStatusBadRequest;
            response.requestId = header.requestId;
            response.json = "{\"ok\":false,\"error\":\"invalid BGRA32 request\"}";
            sendResponse(pipe, response);
            break;
        }
        Request request;
        request.requestId = header.requestId;
        request.width = header.width;
        request.height = header.height;
        request.pixels.resize(header.payloadBytes);
        if (!readExact(pipe, request.pixels.data(), request.pixels.size())) break;
        if (header.stride != header.width * 4u) {
            std::vector<std::uint8_t> packed(static_cast<std::size_t>(header.width) * header.height * 4);
            for (std::uint32_t y = 0; y < header.height; ++y) {
                std::memcpy(packed.data() + static_cast<std::size_t>(y) * header.width * 4,
                            request.pixels.data() + static_cast<std::size_t>(y) * header.stride,
                            static_cast<std::size_t>(header.width) * 4);
            }
            request.pixels = std::move(packed);
        }
        try {
            auto future = queue.submit(std::move(request));
            sendResponse(pipe, future.get());
        } catch (const std::exception& error) {
            Response response;
            response.status = kStatusBusy;
            response.requestId = header.requestId;
            response.json = "{\"ok\":false,\"error\":\"" + jsonEscape(error.what()) + "\"}";
            sendResponse(pipe, response);
        }
    }
    FlushFileBuffers(pipe);
    DisconnectNamedPipe(pipe);
    CloseHandle(pipe);
}

HANDLE createPipe(const std::wstring& name) {
    return CreateNamedPipeW(name.c_str(), PIPE_ACCESS_DUPLEX,
                             PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                             PIPE_UNLIMITED_INSTANCES, 1 << 20, 1 << 20, 0, nullptr);
}

int runServer(const Config& config) {
    OcrQueue queue(config.queueDepth);
    OcrWorker worker(config, queue);
    worker.waitReady();
    std::cout << "pixpin_ocr_service ready\n";
    std::cout << "pipe=";
    std::wcout << config.pipeName;
    std::cout << "\n";
    std::cout.flush();

    while (true) {
        HANDLE pipe = createPipe(config.pipeName);
        if (pipe == INVALID_HANDLE_VALUE) throw std::runtime_error("CreateNamedPipeW failed: " + std::to_string(GetLastError()));
        const BOOL connected = ConnectNamedPipe(pipe, nullptr) ? TRUE : (GetLastError() == ERROR_PIPE_CONNECTED);
        if (!connected) {
            CloseHandle(pipe);
            throw std::runtime_error("ConnectNamedPipe failed: " + std::to_string(GetLastError()));
        }
        std::thread(handleClient, pipe, std::ref(queue), config.maxFrameBytes).detach();
    }
}

} // namespace

int main(int argc, char** argv) {
    try {
        return runServer(parseConfig(argc, argv));
    } catch (const std::exception& error) {
        std::cerr << "pixpin_ocr_service: " << error.what() << '\n';
        return 1;
    }
}
