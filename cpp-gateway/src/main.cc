#include <drogon/drogon.h>
#include <cstdlib>
#include <exception>
#include <functional>
#include <string>

int main() {
    uint16_t port = 8080;
    if (const char* envPort = std::getenv("GATEWAY_PORT")) {
        try {
            int parsed = std::stoi(envPort);
            if (parsed > 0 && parsed <= 65535) {
                port = static_cast<uint16_t>(parsed);
            }
        } catch (const std::exception&) {
            port = 8080;
        }
    }

    drogon::app().registerHandler(
        "/health",
        [](const drogon::HttpRequestPtr&,
           std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
            Json::Value body;
            body["status"] = "ok";
            body["service"] = "gateway";
            body["version"] = "0.1.0";
            auto response = drogon::HttpResponse::newHttpJsonResponse(body);
            response->setStatusCode(drogon::k200OK);
            callback(response);
        },
        {drogon::Get}
    );

    drogon::app().addListener("0.0.0.0", port).setThreadNum(1).run();
    return 0;
}
