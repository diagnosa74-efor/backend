import os
from flask import Flask, jsonify, render_template, request, redirect
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Init Firebase
cred = credentials.Certificate(
    {
        "type": "service_account",
        "project_id": os.environ["FIREBASE_PROJECT_ID"],
        "private_key_id": os.environ["FIREBASE_PRIVATE_KEY_ID"],
        "private_key": os.environ["FIREBASE_PRIVATE_KEY"],
        "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
        "client_id": os.environ["FIREBASE_CLIENT_ID"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": os.environ["FIREBASE_CLIENT_CERT"],
        "universe_domain": "googleapis.com",
    }
)

firebase_admin.initialize_app(cred)

db = firestore.client()


# ===========================
# ROUTE GEJALA
# ===========================
@app.route("/", methods=["GET", "POST"])
def gejala():
    if request.method == "POST":
        kode = request.form["kode"]
        nama = request.form["nama"]
        bobot = request.form["bobot"]  # string sesuai permintaan

        db.collection("gejala").add({"kode": kode, "nama": nama, "bobot": bobot})
        return redirect("/")

    all_gejala = db.collection("gejala").get()
    gejala_list = [g.to_dict() for g in all_gejala]

    return render_template("gejala.html", gejala=gejala_list)


# ===========================
# ROUTE PENYAKIT
# ===========================
@app.route("/penyakit", methods=["GET", "POST"])
def penyakit():
    if request.method == "POST":
        kode = request.form["kode"]
        nama = request.form["nama"]
        gejala = request.form.getlist("gejala")  # multi select

        db.collection("penyakit").add(
            {"kode": kode, "nama": nama, "gejala": gejala}  # list
        )
        return redirect("/penyakit")

    all_gejala = db.collection("gejala").get()
    gejala_list = [{"id": g.id, **g.to_dict()} for g in all_gejala]  # pyright: ignore
    gejala_map = {
        g.to_dict()["kode"]: g.to_dict()["nama"] for g in all_gejala
    }  # pyright: ignore
    all_penyakit = db.collection("penyakit").get()
    penyakit = []
    for p in all_penyakit:
        data = p.to_dict()
        kode_list = data.get("gejala", [])  # pyright: ignore
        nama_gejala = [gejala_map.get(k, "Unknown") for k in kode_list]
        penyakit.append({**data, "gejala": nama_gejala})  # pyright: ignore

    return render_template("penyakit.html", gejala=gejala_list, penyakit=penyakit)


@app.route("/api/cbr", methods=["POST"])
def cbr_sorgenfrei_weighted():
    data = request.json
    gejala_input = data.get("gejala", [])  # pyright: ignore
    if not gejala_input:
        return jsonify({"error": "gejala harus diisi"}), 400

    # --- Load all gejala with weight ---
    gejala_docs = db.collection("gejala").get()
    gejala_map = {}  # kode → bobot float

    for g in gejala_docs:
        d = g.to_dict()
        gejala_map[d["kode"]] = float(d.get("bobot", "0"))  # pyright: ignore

    A = set(gejala_input)

    # --- Ambil penyakit ---
    penyakit_docs = db.collection("penyakit").get()

    hasil = []

    for p in penyakit_docs:
        p_data = p.to_dict()
        B = set(p_data.get("gejala", []))  # pyright: ignore

        # ==== Hitung bobot ====
        # cocok
        a = sum(gejala_map.get(g, 0) for g in (A & B))

        # input tidak ada di penyakit
        b = sum(gejala_map.get(g, 0) for g in (A - B))

        # penyakit tidak dipilih user
        c = sum(gejala_map.get(g, 0) for g in (B - A))

        if a == 0:
            so = 0.0
        else:
            so = (a * a) / ((a + b) * (a + c))

        hasil.append(
            {
                "kode": p_data.get("kode"),  # pyright: ignore
                "nama": p_data.get("nama"),  # pyright: ignore
                "similarity": round(so, 4),
                "a_cocok_weight": round(a, 4),
                "b_input_not_in_penyakit": round(b, 4),
                "c_penyakit_not_in_input": round(c, 4),
                "gejala_penyakit": list(B),
            }
        )

    hasil_sorted = sorted(hasil, key=lambda x: x["similarity"], reverse=True)

    return jsonify(
        {
            "input_gejala": gejala_input,
            "hasil": hasil_sorted,
            "diagnosis": hasil_sorted[0] if hasil_sorted else None,
        }
    )
