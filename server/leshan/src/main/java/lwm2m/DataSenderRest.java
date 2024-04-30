package lwm2m;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpRequest.BodyPublishers;
import java.net.http.HttpResponse.BodyHandlers;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class DataSenderRest {

    private static final Logger logger = LoggerFactory.getLogger(DataSenderRest.class);
    private HttpClient client;
    private static final String BASE_URI = System.getenv("DATA_SENDER_URI");

    public DataSenderRest() {
        client = HttpClient.newHttpClient();
    }

    public void sendData(String data) {
        String uri = (BASE_URI != null ? BASE_URI : "http://localhost:8000") +
                                                    "/api/endpointdata/";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(uri))
                .header("Content-Type", "application/json")
                .POST(BodyPublishers.ofString(data))
                .build();

        logger.debug("DataSenderRest: {}", data);

        client.sendAsync(request, BodyHandlers.ofString())
              .thenApply(response -> {
                  if (response.statusCode() >= 200 && response.statusCode() < 300) {
                      return response.body();
                  } else {
                      logger.error("Request failed with: {}", response.statusCode());
                      logger.error("Payload: {}", data);
                      return null;
                  }
              })
              .exceptionally(e -> {
                  logger.error("Request failed", e);
                  return null;
              });
    }
}
