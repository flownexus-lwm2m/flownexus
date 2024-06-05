package lwm2m;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpRequest.BodyPublishers;
import java.net.http.HttpResponse.BodyHandlers;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

final class ApiPath {
    private final String path;

    private ApiPath(String path) {
        this.path = path;
    }

    public String getPath() {
        return path;
    }

    /* Static factory method for creating instance of ApiPath */
    public static final ApiPath SINGLE_RES = new ApiPath("/leshan_api/resource/single");
    public static final ApiPath COMPOSITE_RES = new ApiPath("/leshan_api/resource/composite");

    @Override
    public String toString() {
        return path;
    }
}

public class DataSenderRest {
    private static final Logger log = LoggerFactory.getLogger(DataSenderRest.class);
    private HttpClient client;
    private ObjectMapper mapper;
    private static final String BASE_URI = (System.getenv("DATA_SENDER_URI") != null ?
                                            System.getenv("DATA_SENDER_URI") :
                                            "http://0.0.0.0:8000");

    public DataSenderRest() {
        client = HttpClient.newHttpClient();
        mapper = new ObjectMapper();
        mapper.enable(SerializationFeature.INDENT_OUTPUT);
    }

    public void sendData(ApiPath apiPath, Object jsonData) {
        /* Prepare request data */
        HttpRequest request = null;
        mapper.enable(SerializationFeature.INDENT_OUTPUT);
        try {
            String data = mapper.writeValueAsString(jsonData);
            request = HttpRequest.newBuilder()
                     .uri(URI.create(BASE_URI + apiPath.getPath()))
                     .header("Content-Type", "application/json")
                     .POST(HttpRequest.BodyPublishers.ofString(data))
                     .build();

            log.trace("POST to {}:\n{}", request.uri(), data);


        } catch (Exception e) {
            log.error("Error in converting object to JSON", e);
            return;
        }

        /* Send request asynchronously */
        client.sendAsync(request, BodyHandlers.ofString())
              .thenApply(response -> {
                  if (response.statusCode() >= 200 && response.statusCode() < 300) {
                      return response.body();
                  } else {
                      log.error("Request failed with: {}", response.statusCode());
                      return null;
                  }
              })
              .exceptionally(e -> {
                  log.error("Request failed", e);
                  return null;
              });
    }
}
