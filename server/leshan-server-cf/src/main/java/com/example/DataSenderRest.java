package com.example;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpRequest.BodyPublishers;
import java.net.http.HttpResponse.BodyHandlers;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class DataSenderRest {

    private static final Logger logger = LoggerFactory.getLogger(DataSenderRest.class);
    private HttpClient client;

    public DataSenderRest() {
        client = HttpClient.newHttpClient();
    }

    public void sendData(String data) {
        logger.info("DataSenderRest: {}", data);
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create("http://127.0.0.1:8000/api/add/"))
                .header("Content-Type", "application/json")
                .POST(BodyPublishers.ofString(data)) // Construct a request with the provided data
                .build();

        System.out.println("DataSenderRest: " + data);
        client.sendAsync(request, BodyHandlers.ofString())
              .thenApply(HttpResponse::body)
              //.thenAccept(responseBody -> logger.info("Successful response: {}", responseBody))
              .exceptionally(e -> {
                  //logger.error("Request failed", e);
                  return null;
              });
    }
}
