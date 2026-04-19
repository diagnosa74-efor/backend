import os
from flask import Flask, jsonify, render_template, request, redirect
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Firebase init
cred = credentials.Certificate(
    {
        "type": "service_account",
        "project_id": os.environ["FIREBASE_PROJECT_ID"],
        "private_key_id": os.environ["FIREBASE_PRIVATE_KEY_ID"],
        "private_key": os.environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
        "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
        "client_id": os.environ["FIREBASE_CLIENT_ID"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_x509_cert_url": os.environ["FIREBASE_CLIENT_CERT"],
    }
)

firebase_admin.initialize_app(cred)
db = firestore.client()


# ===========================
# GEJALA
# ===========================
@app.route("/", methods=["GET", "POST"])
def gejala():
    if request.method == "POST":
        db.collection("gejala").add(
            {
                "kode": request.form["kode"],
                "nama": request.form["nama"],
                "bobot": float(request.form["bobot"].replace(",", ".")),
            }
        )
        return redirect("/")

    data = db.collection("gejala").get()
    gejala = [{"id": g.id, **g.to_dict()} for g in data]

    return render_template("gejala.html", gejala=gejala)


@app.route("/gejala/edit/<id>", methods=["GET", "POST"])
def edit_gejala(id):
    ref = db.collection("gejala").document(id)

    if request.method == "POST":
        ref.update(
            {
                "kode": request.form["kode"],
                "nama": request.form["nama"],
                "bobot": float(request.form["bobot"].replace(",", ".")),
            }
        )
        return redirect("/")

    data = ref.get().to_dict()
    return render_template("edit_gejala.html", gejala=data, id=id)


@app.route("/gejala/delete/<id>")
def delete_gejala(id):
    db.collection("gejala").document(id).delete()
    return redirect("/")


# ===========================
# PENYAKIT
# ===========================
@app.route("/penyakit", methods=["GET", "POST"])
def penyakit():
    if request.method == "POST":
        db.collection("penyakit").add(
            {
                "kode": request.form["kode"],
                "nama": request.form["nama"],
                "gejala": request.form.getlist("gejala"),
                "pencegahan": request.form["pencegahan"],
            }
        )
        return redirect("/penyakit")

    gejala_docs = db.collection("gejala").get()
    gejala_list = [{"id": g.id, **g.to_dict()} for g in gejala_docs]
    gejala_map = {g.to_dict()["kode"]: g.to_dict()["nama"] for g in gejala_docs}

    penyakit_docs = db.collection("penyakit").get()
    penyakit = []

    for p in penyakit_docs:
        data = p.to_dict()
        kode_list = data.get("gejala", [])
        nama_gejala = [gejala_map.get(k, "-") for k in kode_list]

        penyakit.append(
            {
                "id": p.id,
                **data,
                "gejala": nama_gejala,
                "pencegahan": data.get("pencegahan", "-"),
            }
        )

    return render_template("penyakit.html", gejala=gejala_list, penyakit=penyakit)


@app.route("/penyakit/edit/<id>", methods=["GET", "POST"])
def edit_penyakit(id):
    ref = db.collection("penyakit").document(id)

    if request.method == "POST":
        ref.update(
            {
                "kode": request.form["kode"],
                "nama": request.form["nama"],
                "gejala": request.form.getlist("gejala"),
                "pencegahan": request.form["pencegahan"],
            }
        )
        return redirect("/penyakit")

    penyakit = ref.get().to_dict()
    gejala = db.collection("gejala").get()
    gejala_list = [{"id": g.id, **g.to_dict()} for g in gejala]

    return render_template(
        "edit_penyakit.html", penyakit=penyakit, gejala=gejala_list, id=id
    )


@app.route("/penyakit/delete/<id>")
def delete_penyakit(id):
    db.collection("penyakit").document(id).delete()
    return redirect("/penyakit")


# ===========================
# CBR
# ===========================
@app.route("/api/cbr", methods=["POST"])
def cbr():
    data = request.json
    A = set(data.get("gejala", []))

    gejala_docs = db.collection("gejala").get()
    gejala_map = {
        g.to_dict()["kode"]: float(g.to_dict().get("bobot", 0)) for g in gejala_docs
    }

    penyakit_docs = db.collection("penyakit").get()
    hasil = []

    for p in penyakit_docs:
        p_data = p.to_dict()
        B = set(p_data.get("gejala", []))

        a = sum(gejala_map.get(g, 0) for g in (A & B))
        b = sum(gejala_map.get(g, 0) for g in (A - B))
        c = sum(gejala_map.get(g, 0) for g in (B - A))

        so = 0 if a == 0 else (a * a) / ((a + b) * (a + c))

        hasil.append(
            {
                "nama": p_data.get("nama"),
                "similarity": round(so, 4),
                "pencegahan": p_data.get("pencegahan", "-"),
            }
        )

    hasil.sort(key=lambda x: x["similarity"], reverse=True)

    return jsonify({"hasil": hasil, "diagnosis": hasil[0] if hasil else None})
