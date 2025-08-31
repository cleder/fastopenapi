import re
from collections.abc import Callable
from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.httpexception import HTTPException
from fastopenapi.base_router import BaseRouter


class PyramidRouter(BaseRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending_routes = []

    def add_route(self, path: str, method: str, endpoint: Callable):
        super().add_route(path, method, endpoint)
        self._pending_routes.append((path, method, endpoint))

    def include_into(self, config: Configurator):
        """
        Register all routes and views with the Pyramid Configurator.
        Should be called during Pyramid app setup.
        """
        for path, method, endpoint in self._pending_routes:
            route_name = endpoint.__name__
            pyramid_path = self._convert_path(path)
            config.add_route(route_name, pyramid_path)
            config.add_view(
                self._make_view(endpoint),
                route_name=route_name,
                request_method=method.upper(),
                renderer="json",
            )
        self._register_docs_endpoints(config)

    def _convert_path(self, path: str) -> str:
        # Convert OpenAPI-style {param} to Pyramid :param
        return re.sub(r"{(\w+)}", r":\1", path)

    def _make_view(self, endpoint: Callable):
        def view(request):
            try:
                path_params = request.matchdict or {}
                query_params = request.params or {}
                body = (
                    getattr(request, "json_body", {})
                    if hasattr(request, "json_body")
                    else {}
                )
                all_params = {**query_params, **path_params}
                kwargs = self.resolve_endpoint_params(endpoint, all_params, body)
                result = endpoint(**kwargs)
                meta = getattr(endpoint, "__route_meta__", {})
                status_code = meta.get("status_code", 200)
                result = self._serialize_response(result)
                return Response(json_body=result, status=status_code)
            except HTTPException as e:
                error_response = self.handle_exception(e)
                return Response(json_body=error_response, status=e.code)
            except Exception as e:
                error_response = self.handle_exception(e)
                status = getattr(e, "status_code", 500)
                return Response(json_body=error_response, status=status)

        return view

    def _register_docs_endpoints(self, config: Configurator):
        # Ensure URLs are always strings
        openapi_url = self.openapi_url or "/openapi.json"
        docs_url = self.docs_url or "/docs"
        redoc_url = self.redoc_url or "/redoc"

        # /openapi.json endpoint
        def openapi_view(request):
            return Response(json_body=self.openapi)

        config.add_route("openapi_json", openapi_url)
        config.add_view(
            openapi_view,
            route_name="openapi_json",
            request_method="GET",
            renderer="json",
        )

        # /docs endpoint (Swagger UI)
        def docs_view(request):
            html = self.render_swagger_ui(openapi_url)
            return Response(body=html, content_type="text/html")

        config.add_route("swagger_ui", docs_url)
        config.add_view(docs_view, route_name="swagger_ui", request_method="GET")

        # /redoc endpoint
        def redoc_view(request):
            html = self.render_redoc_ui(openapi_url)
            return Response(body=html, content_type="text/html")

        config.add_route("redoc_ui", redoc_url)
        config.add_view(redoc_view, route_name="redoc_ui", request_method="GET")

    # Decorators for HTTP methods
    def get(self, path: str, **meta):
        def decorator(func: Callable):
            func.__route_meta__ = meta
            self.add_route(path, "GET", func)
            return func

        return decorator

    def post(self, path: str, **meta):
        def decorator(func: Callable):
            func.__route_meta__ = meta
            self.add_route(path, "POST", func)
            return func

        return decorator

    def put(self, path: str, **meta):
        def decorator(func: Callable):
            func.__route_meta__ = meta
            self.add_route(path, "PUT", func)
            return func

        return decorator

    def patch(self, path: str, **meta):
        def decorator(func: Callable):
            func.__route_meta__ = meta
            self.add_route(path, "PATCH", func)
            return func

        return decorator

    def delete(self, path: str, **meta):
        def decorator(func: Callable):
            func.__route_meta__ = meta
            self.add_route(path, "DELETE", func)
            return func

        return decorator
