/* Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Parts of this code are based on the Leshan project
 * (https://www.eclipse.org/leshan/) licensed under the BSD 3-Clause License.
 */

package lwm2m.servlet;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.eclipse.leshan.core.node.InvalidLwM2mPathException;
import org.eclipse.leshan.core.node.LwM2mPath;
import org.eclipse.leshan.core.node.LwM2mSingleResource;
import org.eclipse.leshan.core.node.codec.CodecException;
import org.eclipse.leshan.core.request.ContentFormat;
import org.eclipse.leshan.core.request.DownlinkDeviceManagementRequest;
import org.eclipse.leshan.core.request.ExecuteRequest;
import org.eclipse.leshan.core.request.ReadRequest;
import org.eclipse.leshan.core.request.WriteRequest;
import org.eclipse.leshan.core.request.exception.ClientSleepingException;
import org.eclipse.leshan.core.request.exception.InvalidRequestException;
import org.eclipse.leshan.core.request.exception.InvalidResponseException;
import org.eclipse.leshan.core.request.exception.RequestCanceledException;
import org.eclipse.leshan.core.request.exception.RequestRejectedException;
import org.eclipse.leshan.core.response.LwM2mResponse;
import org.eclipse.leshan.core.response.ReadResponse;
import org.eclipse.leshan.server.LeshanServer;
import org.eclipse.leshan.server.registration.Registration;

import com.fasterxml.jackson.databind.ObjectMapper;

import lwm2m.json.SingleResourceParser;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Command API for Django: /api/clients/{endpoint}/{path}.
 *
 * GET reads a path, PUT writes a single resource, POST executes a resource.
 * doc/source/architecture/gateway_contract.rst describes the status codes.
 */
public class CommandServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;
    private static final Logger log = LoggerFactory.getLogger(CommandServlet.class);
    private static final long DEFAULT_TIMEOUT_S = 5;

    private final transient LeshanServer server;
    private final transient ObjectMapper mapper;

    public CommandServlet(LeshanServer server, ObjectMapper mapper) {
        this.server = server;
        this.mapper = mapper;
    }

    private record Target(Registration registration, String path) {
    }

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        Target target = target(req, resp, false);
        if (target != null) {
            send(req, resp, target, format -> new ReadRequest(format, target.path()));
        }
    }

    @Override
    protected void doPut(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        Target target = target(req, resp, true);
        if (target == null) {
            return;
        }
        LwM2mSingleResource node;
        try {
            node = SingleResourceParser.parse(mapper.readTree(req.getInputStream()));
        } catch (IOException | IllegalArgumentException e) {
            respond(resp, HttpServletResponse.SC_BAD_REQUEST, error("invalid resource: " + e.getMessage()));
            return;
        }
        LwM2mPath path = new LwM2mPath(target.path());
        if (!path.isResource()) {
            respond(resp, HttpServletResponse.SC_BAD_REQUEST, error("only a single resource can be written"));
            return;
        }
        if (node.getId() != path.getResourceId()) {
            respond(resp, HttpServletResponse.SC_BAD_REQUEST,
                    error("resource id " + node.getId() + " does not match the path " + target.path()));
            return;
        }
        send(req, resp, target,
                format -> new WriteRequest(WriteRequest.Mode.REPLACE, format, target.path(), node));
    }

    @Override
    protected void doPost(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        Target target = target(req, resp, true);
        if (target != null) {
            String arguments = new String(req.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            send(req, resp, target,
                    format -> new ExecuteRequest(target.path(), arguments.isEmpty() ? null : arguments));
        }
    }

    /** Parse /{endpoint}/{path} and look up the registration; respond and return null on error. */
    private Target target(HttpServletRequest req, HttpServletResponse resp, boolean resourceOnly) throws IOException {
        String info = req.getPathInfo() == null ? "" : req.getPathInfo();
        int split = info.indexOf('/', 1);
        if (split < 0) {
            respond(resp, HttpServletResponse.SC_BAD_REQUEST, error("expected /{endpoint}/{path}"));
            return null;
        }
        String endpoint = info.substring(1, split);
        String path = info.substring(split);
        try {
            LwM2mPath parsed = new LwM2mPath(path);
            if (resourceOnly && !parsed.isResource() && !parsed.isResourceInstance()) {
                respond(resp, HttpServletResponse.SC_BAD_REQUEST, error("expected a resource path: " + path));
                return null;
            }
        } catch (InvalidLwM2mPathException e) {
            respond(resp, HttpServletResponse.SC_BAD_REQUEST, error("invalid path: " + path));
            return null;
        }
        Registration registration = server.getRegistrationService().getByEndpoint(endpoint);
        if (registration == null) {
            respond(resp, HttpServletResponse.SC_NOT_FOUND, error("no registered client " + endpoint));
            return null;
        }
        return new Target(registration, path);
    }

    /** Builds the Leshan request inside send(), so that Leshan's validation errors become 400. */
    private interface RequestFactory {
        DownlinkDeviceManagementRequest<? extends LwM2mResponse> create(ContentFormat format);
    }

    private void send(HttpServletRequest req, HttpServletResponse resp, Target target, RequestFactory factory)
            throws IOException {
        ContentFormat format;
        long timeout;
        try {
            format = parseFormat(req.getParameter("format"));
            timeout = parseTimeout(req.getParameter("timeout"));
        } catch (IllegalArgumentException e) {
            respond(resp, HttpServletResponse.SC_BAD_REQUEST, error(e.getMessage()));
            return;
        }
        LwM2mResponse response;
        try {
            response = server.send(target.registration(), factory.create(format), timeout * 1000);
        } catch (InvalidRequestException | CodecException | IllegalArgumentException e) {
            respond(resp, HttpServletResponse.SC_BAD_REQUEST, error("invalid request: " + e.getMessage()));
            return;
        } catch (ClientSleepingException | RequestRejectedException | RequestCanceledException e) {
            respond(resp, HttpServletResponse.SC_SERVICE_UNAVAILABLE, error(e.getMessage()));
            return;
        } catch (InvalidResponseException e) {
            respond(resp, HttpServletResponse.SC_BAD_GATEWAY, error("invalid device response: " + e.getMessage()));
            return;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            respond(resp, HttpServletResponse.SC_SERVICE_UNAVAILABLE, error("interrupted"));
            return;
        }

        Result result = result(response, timeout);
        if (result.status() != HttpServletResponse.SC_OK) {
            log.warn("{} {} failed: {}", req.getMethod(), req.getPathInfo(), result.body());
        }
        respond(resp, result.status(), result.body());
    }

    record Result(int status, Map<String, Object> body) {
    }

    /** Map a device response, or null for no response within timeout, to the HTTP answer. */
    static Result result(LwM2mResponse response, long timeout) {
        if (response == null) {
            return new Result(HttpServletResponse.SC_GATEWAY_TIMEOUT,
                    error("no device response within " + timeout + " s"));
        }
        Map<String, Object> body = new LinkedHashMap<>();
        int code = response.getCode().getCode();
        body.put("status", response.getCode().getName());
        body.put("code", String.format("%d.%02d", code / 100, code % 100));
        if (response instanceof ReadResponse read && read.getContent() != null) {
            body.put("content", read.getContent());
        }
        if (response.isSuccess()) {
            return new Result(HttpServletResponse.SC_OK, body);
        }
        if (response.getErrorMessage() != null && !response.getErrorMessage().isEmpty()) {
            body.put("error", response.getErrorMessage());
        }
        return new Result(HttpServletResponse.SC_BAD_GATEWAY, body);
    }

    private static Map<String, Object> error(String message) {
        return Map.of("error", message == null ? "" : message);
    }

    static ContentFormat parseFormat(String name) {
        if (name == null) {
            return null;
        }
        ContentFormat format = ContentFormat.fromName(name.toUpperCase());
        if (format == null) {
            throw new IllegalArgumentException("unknown format: " + name);
        }
        return format;
    }

    static long parseTimeout(String value) {
        if (value == null) {
            return DEFAULT_TIMEOUT_S;
        }
        long timeout;
        try {
            timeout = Long.parseLong(value);
        } catch (NumberFormatException e) {
            timeout = 0;
        }
        if (timeout <= 0) {
            throw new IllegalArgumentException("timeout must be a positive number of seconds: " + value);
        }
        return timeout;
    }

    private void respond(HttpServletResponse resp, int status, Object body) throws IOException {
        resp.setStatus(status);
        resp.setContentType("application/json");
        resp.getOutputStream().write(mapper.writeValueAsBytes(body));
    }
}
