#include <drogon/drogon.h>
#include <drogon/MultiPart.h>

#include <chrono>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <functional>
#include <random>
#include <sstream>
#include <string>

namespace fs = std::filesystem;

static std::string makeTraceId() {
    static thread_local std::mt19937_64 rng(std::random_device{}());
    std::uniform_int_distribution<unsigned long long> dist;

    auto now = std::chrono::steady_clock::now().time_since_epoch().count();

    std::ostringstream oss;
    oss << std::hex << now << dist(rng);
    return oss.str();
}

static std::string pickTraceId(const drogon::HttpRequestPtr &req) {
    auto traceId = req->getHeader("x-trace-id");
    if (traceId.empty()) {
        traceId = makeTraceId();
    }
    return traceId;
}

static std::string sanitizeFilename(const std::string &name) {
    std::string out = name;
    for (auto &ch : out) {
        bool ok = (ch >= 'a' && ch <= 'z') ||
                  (ch >= 'A' && ch <= 'Z') ||
                  (ch >= '0' && ch <= '9') ||
                  ch == '.' || ch == '_' || ch == '-';
        if (!ok) {
            ch = '_';
        }
    }
    if (out.empty()) {
        out = "upload.txt";
    }
    return out;
}

static std::string makeStoredFilename(const std::string &originalName) {
    static thread_local std::mt19937_64 rng(std::random_device{}());
    std::uniform_int_distribution<unsigned long long> dist;

    std::string safe = sanitizeFilename(originalName);
    std::string stem = safe;
    std::string ext;

    auto pos = safe.rfind('.');
    if (pos != std::string::npos && pos > 0) {
        stem = safe.substr(0, pos);
        ext = safe.substr(pos);
    }

    auto now = std::chrono::system_clock::now().time_since_epoch().count();

    std::ostringstream oss;
    oss << stem << "_" << now << "_" << std::hex << dist(rng) << ext;
    return oss.str();
}

static drogon::HttpResponsePtr makeJsonError(
    drogon::HttpStatusCode code,
    const std::string &message,
    const std::string &traceId = "") {
    Json::Value err;
    err["error"] = message;

    auto resp = drogon::HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(code);

    if (!traceId.empty()) {
        resp->addHeader("x-trace-id", traceId);
    }
    return resp;
}

static drogon::HttpResponsePtr makeJsonProxyResponse(
    const drogon::HttpResponsePtr &upstreamResp,
    const std::string &traceId,
    long long upstreamMs) {
    auto outResp = drogon::HttpResponse::newHttpResponse();
    outResp->setStatusCode(upstreamResp->statusCode());
    outResp->setContentTypeCode(drogon::CT_APPLICATION_JSON);
    outResp->setBody(std::string(upstreamResp->body()));

    outResp->addHeader("x-trace-id", traceId);
    outResp->addHeader("x-upstream-ms", std::to_string(upstreamMs));

    const auto xCache = upstreamResp->getHeader("x-cache");
    if (!xCache.empty()) {
        outResp->addHeader("x-cache", xCache);
    }

    const auto xKbVersion = upstreamResp->getHeader("x-kb-version");
    if (!xKbVersion.empty()) {
        outResp->addHeader("x-kb-version", xKbVersion);
    }

    return outResp;
}

int main() {
    uint16_t gatewayPort = 8080;
    if (const char *envPort = std::getenv("GATEWAY_PORT")) {
        try {
            int parsed = std::stoi(envPort);
            if (parsed > 0 && parsed <= 65535) {
                gatewayPort = static_cast<uint16_t>(parsed);
            }
        } catch (const std::exception &) {
            gatewayPort = 8080;
        }
    }

    std::string aiHost = "ai-service";
    if (const char *envAiHost = std::getenv("AI_SERVICE_HOST")) {
        aiHost = envAiHost;
    }

    uint16_t aiPort = 8000;
    if (const char *envAiPort = std::getenv("AI_SERVICE_PORT")) {
        try {
            int parsed = std::stoi(envAiPort);
            if (parsed > 0 && parsed <= 65535) {
                aiPort = static_cast<uint16_t>(parsed);
            }
        } catch (const std::exception &) {
            aiPort = 8000;
        }
    }

    std::string uploadDir = "/workspace/uploads";
    if (const char *envUploadDir = std::getenv("UPLOAD_DIR")) {
        uploadDir = envUploadDir;
    }

    fs::create_directories(uploadDir);

    const std::string aiBaseUrl =
        "http://" + aiHost + ":" + std::to_string(aiPort);

    auto aiClient = drogon::HttpClient::newHttpClient(aiBaseUrl);

    drogon::app().registerHandler(
        "/health",
        [](const drogon::HttpRequestPtr &,
           std::function<void(const drogon::HttpResponsePtr &)> &&callback) {
            Json::Value body;
            body["status"] = "ok";
            body["service"] = "gateway";
            body["version"] = "0.1.0";
            auto response = drogon::HttpResponse::newHttpJsonResponse(body);
            response->setStatusCode(drogon::k200OK);
            callback(response);
        },
        {drogon::Get});

    drogon::app().registerHandler(
        "/rag/query",
        [aiClient](const drogon::HttpRequestPtr &req,
                   std::function<void(const drogon::HttpResponsePtr &)> &&callback) {
            const auto traceId = pickTraceId(req);
            const auto startedAt = std::chrono::steady_clock::now();

            auto requestJson = req->getJsonObject();
            if (!requestJson) {
                callback(makeJsonError(drogon::k400BadRequest, "invalid json body", traceId));
                return;
            }

            if (!requestJson->isMember("question") ||
                !(*requestJson)["question"].isString()) {
                callback(makeJsonError(
                    drogon::k400BadRequest,
                    "field 'question' is required and must be a string",
                    traceId));
                return;
            }

            Json::Value forwardBody;
            forwardBody["question"] = (*requestJson)["question"].asString();

            if (requestJson->isMember("topK") && (*requestJson)["topK"].isInt()) {
                forwardBody["topK"] = (*requestJson)["topK"].asInt();
            } else {
                forwardBody["topK"] = 3;
            }

            if (requestJson->isMember("docScope") && (*requestJson)["docScope"].isArray()) {
                forwardBody["docScope"] = (*requestJson)["docScope"];
            } else {
                forwardBody["docScope"] = Json::arrayValue;
            }

            auto forwardReq = drogon::HttpRequest::newHttpJsonRequest(forwardBody);
            forwardReq->setMethod(drogon::Post);
            forwardReq->setPath("/internal/query");
            forwardReq->addHeader("x-trace-id", traceId);

            aiClient->sendRequest(
                forwardReq,
                [callback = std::move(callback), traceId, startedAt](
                    drogon::ReqResult result,
                    const drogon::HttpResponsePtr &resp) mutable {
                    auto upstreamMs = std::chrono::duration_cast<std::chrono::milliseconds>(
                                          std::chrono::steady_clock::now() - startedAt)
                                          .count();

                    if (result != drogon::ReqResult::Ok || !resp) {
                        auto gatewayResp = makeJsonError(
                            drogon::k502BadGateway,
                            "failed to call internal ai service",
                            traceId);
                        gatewayResp->addHeader("x-upstream-ms", std::to_string(upstreamMs));
                        callback(gatewayResp);
                        return;
                    }

                    callback(makeJsonProxyResponse(resp, traceId, upstreamMs));
                });
        },
        {drogon::Post});

    drogon::app().registerHandler(
        "/docs/upload",
        [aiClient, uploadDir](const drogon::HttpRequestPtr &req,
                              std::function<void(const drogon::HttpResponsePtr &)> &&callback) {
            const auto traceId = pickTraceId(req);
            const auto startedAt = std::chrono::steady_clock::now();

            drogon::MultiPartParser fileParser;
            int parseResult = fileParser.parse(req);
            if (parseResult != 0) {
                callback(makeJsonError(drogon::k400BadRequest, "failed to parse multipart form", traceId));
                return;
            }

            const auto &files = fileParser.getFiles();
            if (files.empty()) {
                callback(makeJsonError(drogon::k400BadRequest, "field 'file' is required", traceId));
                return;
            }

            const auto &file = files[0];
            const std::string originalName = file.getFileName();
            const std::string storedName = makeStoredFilename(originalName);
            const fs::path savedPath = fs::path(uploadDir) / storedName;

            try {
                file.saveAs(savedPath.string());
            } catch (const std::exception &e) {
                callback(makeJsonError(drogon::k500InternalServerError, e.what(), traceId));
                return;
            }

            std::string title = fileParser.getParameter<std::string>("title");
            if (title.empty()) {
                title = originalName;
            }

            std::string owner = fileParser.getParameter<std::string>("owner");
            if (owner.empty()) {
                owner = "demo";
            }

            Json::Value forwardBody;
            forwardBody["sourcePath"] = savedPath.string();
            forwardBody["title"] = title;
            forwardBody["owner"] = owner;

            auto forwardReq = drogon::HttpRequest::newHttpJsonRequest(forwardBody);
            forwardReq->setMethod(drogon::Post);
            forwardReq->setPath("/internal/docs/upload");
            forwardReq->addHeader("x-trace-id", traceId);

            aiClient->sendRequest(
                forwardReq,
                [callback = std::move(callback), traceId, startedAt](
                    drogon::ReqResult result,
                    const drogon::HttpResponsePtr &resp) mutable {
                    auto upstreamMs = std::chrono::duration_cast<std::chrono::milliseconds>(
                                          std::chrono::steady_clock::now() - startedAt)
                                          .count();

                    if (result != drogon::ReqResult::Ok || !resp) {
                        auto gatewayResp = makeJsonError(
                            drogon::k502BadGateway,
                            "failed to call internal upload service",
                            traceId);
                        gatewayResp->addHeader("x-upstream-ms", std::to_string(upstreamMs));
                        callback(gatewayResp);
                        return;
                    }

                    callback(makeJsonProxyResponse(resp, traceId, upstreamMs));
                });
        },
        {drogon::Post});

    drogon::app().registerHandler(
        "/tasks/{1}",
        [aiClient](const drogon::HttpRequestPtr &req,
                   std::function<void(const drogon::HttpResponsePtr &)> &&callback,
                   const std::string &taskId) {
            const auto traceId = pickTraceId(req);
            const auto startedAt = std::chrono::steady_clock::now();

            auto forwardReq = drogon::HttpRequest::newHttpRequest();
            forwardReq->setMethod(drogon::Get);
            forwardReq->setPath("/internal/tasks/" + taskId);
            forwardReq->addHeader("x-trace-id", traceId);

            aiClient->sendRequest(
                forwardReq,
                [callback = std::move(callback), traceId, startedAt](
                    drogon::ReqResult result,
                    const drogon::HttpResponsePtr &resp) mutable {
                    auto upstreamMs = std::chrono::duration_cast<std::chrono::milliseconds>(
                                          std::chrono::steady_clock::now() - startedAt)
                                          .count();

                    if (result != drogon::ReqResult::Ok || !resp) {
                        auto gatewayResp = makeJsonError(
                            drogon::k502BadGateway,
                            "failed to call internal task service",
                            traceId);
                        gatewayResp->addHeader("x-upstream-ms", std::to_string(upstreamMs));
                        callback(gatewayResp);
                        return;
                    }

                    callback(makeJsonProxyResponse(resp, traceId, upstreamMs));
                });
        },
        {drogon::Get});

    size_t maxBodySize = 20 * 1024 * 1024;
    if (const char *envBodySizeMb = std::getenv("GATEWAY_MAX_BODY_SIZE_MB")) {
        try {
            int parsed = std::stoi(envBodySizeMb);
            if (parsed > 0) {
                maxBodySize = static_cast<size_t>(parsed) * 1024 * 1024;
            }
        } catch (const std::exception &) {
            maxBodySize = 20 * 1024 * 1024;
        }
    }

    drogon::app().setClientMaxBodySize(maxBodySize);

    LOG_INFO << "gateway starting on port=" << gatewayPort
             << " aiBaseUrl=" << aiBaseUrl
             << " uploadDir=" << uploadDir
             << " maxBodySize=" << maxBodySize;

    drogon::app().addListener("0.0.0.0", gatewayPort).setThreadNum(1).run();
    return 0;
}
