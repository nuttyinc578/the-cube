package com.nuttyinc.cpe;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Locale;

/**
 * Java command client for CPE/1.
 *
 * <p>Java sends a bounded JSON command to Node. Node compiles it into numeric
 * CPE/1 instructions, and the embedded Python engine applies those numbers to
 * Pymunk, Pygame, and IPE. Arbitrary Java or Python source is never executed.</p>
 */
public final class CpeClient {
    private final HttpClient client;
    private final URI commandEndpoint;

    public CpeClient(String aspireIp, int nodePort) {
        if (nodePort < 1 || nodePort > 65535) {
            throw new IllegalArgumentException("nodePort must be between 1 and 65535");
        }
        String host = aspireIp == null || aspireIp.isBlank() ? "127.0.0.1" : aspireIp.trim();
        if (host.contains(":") && !host.startsWith("[")) {
            host = "[" + host + "]";
        }
        this.commandEndpoint = URI.create("http://" + host + ":" + nodePort + "/commands");
        this.client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
    }

    public String sendJson(String json) throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder(commandEndpoint)
            .timeout(Duration.ofSeconds(3))
            .header("Content-Type", "application/json")
            .header("Accept", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(json))
            .build();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException("CPE Node bridge returned HTTP " + response.statusCode() + ": " + response.body());
        }
        return response.body();
    }

    public String spawnBox(double x, double y, double size, int red, int green, int blue)
            throws IOException, InterruptedException {
        return spawn("box", x, y, 4, size, red, green, blue);
    }

    public String spawnCircle(double x, double y, double radius, int red, int green, int blue)
            throws IOException, InterruptedException {
        return spawn("circle", x, y, 8, radius, red, green, blue);
    }

    public String spawnPolygon(double x, double y, int sides, double size, int red, int green, int blue)
            throws IOException, InterruptedException {
        return spawn("polygon", x, y, sides, size, red, green, blue);
    }

    private String spawn(String shape, double x, double y, int sides, double size, int red, int green, int blue)
            throws IOException, InterruptedException {
        String json = String.format(
            Locale.ROOT,
            "{\"action\":\"spawn\",\"shape\":\"%s\",\"x\":%.4f,\"y\":%.4f,\"sides\":%d,\"size\":%.4f,\"color\":[%d,%d,%d]}",
            shape, x, y, sides, size, channel(red), channel(green), channel(blue));
        return sendJson(json);
    }

    public String gravity(double x, double y) throws IOException, InterruptedException {
        return sendJson(String.format(Locale.ROOT, "{\"action\":\"gravity\",\"x\":%.4f,\"y\":%.4f}", x, y));
    }

    public String impulse(int entityId, double x, double y) throws IOException, InterruptedException {
        return vectorCommand("impulse", entityId, x, y);
    }

    public String force(int entityId, double x, double y) throws IOException, InterruptedException {
        return vectorCommand("force", entityId, x, y);
    }

    private String vectorCommand(String action, int entityId, double x, double y)
            throws IOException, InterruptedException {
        return sendJson(String.format(
            Locale.ROOT,
            "{\"action\":\"%s\",\"id\":%d,\"x\":%.4f,\"y\":%.4f}",
            action, entityId, x, y));
    }

    public String burst(double x, double y, int count) throws IOException, InterruptedException {
        return sendJson(String.format(
            Locale.ROOT,
            "{\"action\":\"burst\",\"x\":%.4f,\"y\":%.4f,\"count\":%d}",
            x, y, count));
    }

    public String clear() throws IOException, InterruptedException {
        return sendJson("{\"action\":\"clear\"}");
    }

    public String pause(boolean paused) throws IOException, InterruptedException {
        return sendJson("{\"action\":\"pause\",\"paused\":" + paused + "}");
    }

    private static int channel(int value) {
        return Math.max(0, Math.min(255, value));
    }

    public static void main(String[] arguments) throws Exception {
        String host = arguments.length > 0 ? arguments[0] : "127.0.0.1";
        int port = arguments.length > 1 ? Integer.parseInt(arguments[1]) : 4310;
        String action = arguments.length > 2 ? arguments[2].toLowerCase(Locale.ROOT) : "spawn";
        CpeClient cpe = new CpeClient(host, port);
        String response = switch (action) {
            case "burst" -> cpe.burst(550, 240, 60);
            case "clear" -> cpe.clear();
            case "gravity" -> cpe.gravity(0, 550);
            case "pause" -> cpe.pause(true);
            case "resume" -> cpe.pause(false);
            default -> cpe.spawnPolygon(550, 100, 6, 34, 222, 108, 39);
        };
        System.out.println(response);
    }
}
