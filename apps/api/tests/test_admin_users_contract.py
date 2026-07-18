from routes.admin.users import router


def test_admin_users_get_route_is_registered_once():
    matches = [
        route
        for route in router.routes
        if getattr(route, "path", None) == "/users" and "GET" in getattr(route, "methods", set())
    ]
    assert len(matches) == 1
    assert {parameter.name for parameter in matches[0].dependant.query_params} == {
        "q",
        "email",
        "id",
        "plan_slug",
        "limit",
        "offset",
    }
