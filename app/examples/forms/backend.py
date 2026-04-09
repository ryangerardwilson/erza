from erza.backend import error, handler, redirect, route, session


@handler("auth.status")
def auth_status():
    return session().get("status", "Enter your credentials.")


@handler("auth.email")
def auth_email():
    return session().get("email", "")


@route("/auth/login")
def auth_login(email="", password=""):
    state = session()
    state["email"] = email

    if email == "demo@erza.dev" and password == "terminal":
        state["status"] = "Signed in."
        return redirect("done.erza")

    state["status"] = "Invalid credentials."
    return error("Invalid credentials.")
