/* Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package lwm2m;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;

/** Runs IngestClient against a local HTTP server that answers with a list of status codes. */
class IngestClientTest {
    private HttpServer server;
    private IngestClient client;
    private final BlockingQueue<String> bodies = new LinkedBlockingQueue<>();

    private void start(List<Integer> statuses) throws IOException {
        BlockingQueue<Integer> answers = new LinkedBlockingQueue<>(statuses);
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            bodies.add(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            Integer status = answers.poll();
            exchange.sendResponseHeaders(status == null ? 201 : status, -1);
            exchange.close();
        });
        server.start();
        client = new IngestClient("http://127.0.0.1:" + server.getAddress().getPort(), new ObjectMapper(), 10);
    }

    @AfterEach
    void stop() {
        client.stop();
        server.stop(0);
    }

    private List<String> received(int count) throws InterruptedException {
        List<String> received = new java.util.ArrayList<>();
        for (int i = 0; i < count; i++) {
            String body = bodies.poll(5, TimeUnit.SECONDS);
            if (body == null) {
                break;
            }
            received.add(body);
        }
        // Nothing else may arrive after the expected requests
        String extra = bodies.poll(300, TimeUnit.MILLISECONDS);
        if (extra != null) {
            received.add(extra);
        }
        return received;
    }

    @Test
    void retriesServerErrorsUntilAccepted() throws Exception {
        start(List.of(503, 500));
        client.post(IngestClient.REGISTRATION, Map.of("ep", "a"));

        assertEquals(List.of("{\"ep\":\"a\"}", "{\"ep\":\"a\"}", "{\"ep\":\"a\"}"), received(3));
    }

    @Test
    void doesNotRetryClientErrors() throws Exception {
        start(List.of(400));
        client.post(IngestClient.REGISTRATION, Map.of("ep", "a"));

        assertEquals(1, received(1).size());
    }

    @Test
    void dropsTheRequestAfterAllAttempts() throws Exception {
        start(List.of(503, 503, 503, 503, 503, 503, 503));
        client.post(IngestClient.REGISTRATION, Map.of("ep", "a"));

        assertEquals(IngestClient.ATTEMPTS, received(IngestClient.ATTEMPTS).size());
    }
}
