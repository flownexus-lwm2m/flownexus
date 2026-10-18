/* Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package lwm2m;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Posts events to the Django ingest API.
 *
 * A request that fails with a connection error or a 5xx status is retried
 * with exponential backoff, ATTEMPTS times in total, and then dropped. A 4xx
 * status is not retried. Retries are kept in memory only, at most
 * MAX_PENDING_RETRIES at a time, and can reorder requests.
 */
public class IngestClient {
    public static final String REGISTRATION = "/flownexus/ingest/registration";
    public static final String TIMESTAMPED = "/flownexus/ingest/resource/timestamped";

    static final int ATTEMPTS = 6;
    static final long FIRST_RETRY_MS = 2000;
    static final int MAX_PENDING_RETRIES = 10000;

    private static final Logger log = LoggerFactory.getLogger(IngestClient.class);
    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(10);

    private final String baseUri;
    private final ObjectMapper mapper;
    private final long firstRetryMs;
    private final AtomicInteger pendingRetries = new AtomicInteger();
    private final HttpClient client = HttpClient.newBuilder()
            .connectTimeout(REQUEST_TIMEOUT)
            .build();
    private final ScheduledExecutorService retries = Executors.newSingleThreadScheduledExecutor();

    public IngestClient(String baseUri, ObjectMapper mapper) {
        this(baseUri, mapper, FIRST_RETRY_MS);
    }

    IngestClient(String baseUri, ObjectMapper mapper, long firstRetryMs) {
        this.baseUri = baseUri;
        this.mapper = mapper;
        this.firstRetryMs = firstRetryMs;
    }

    public void post(String path, Object body) {
        String data;
        try {
            data = mapper.writeValueAsString(body);
        } catch (JsonProcessingException e) {
            log.error("Cannot serialize request to {}", path, e);
            return;
        }
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUri + path))
                .timeout(REQUEST_TIMEOUT)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(data))
                .build();
        log.trace("POST to {}:\n{}", request.uri(), data);
        send(request, 1);
    }

    private void send(HttpRequest request, int attempt) {
        client.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .whenComplete((response, error) -> {
                    if (error == null && response.statusCode() < 300) {
                        return;
                    }
                    if (error == null && response.statusCode() < 500) {
                        log.error("{} rejected with {}: {}", request.uri(), response.statusCode(),
                                response.body());
                        return;
                    }
                    String reason = error != null ? error.toString() : "HTTP " + response.statusCode();
                    if (attempt >= ATTEMPTS) {
                        log.error("Dropping request to {} after {} attempts: {}", request.uri(), attempt,
                                reason);
                        return;
                    }
                    if (pendingRetries.incrementAndGet() > MAX_PENDING_RETRIES) {
                        pendingRetries.decrementAndGet();
                        log.error("Dropping request to {}: too many pending retries", request.uri());
                        return;
                    }
                    long delay = firstRetryMs << (attempt - 1);
                    log.warn("Request to {} failed ({}), retry in {} ms", request.uri(), reason, delay);
                    retries.schedule(() -> {
                        pendingRetries.decrementAndGet();
                        send(request, attempt + 1);
                    }, delay, TimeUnit.MILLISECONDS);
                });
    }

    public void stop() {
        retries.shutdownNow();
    }
}
