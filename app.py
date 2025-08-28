import io
import re
import zipfile
from typing import List, Tuple

import fitz  # PyMuPDF
import streamlit as st


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", " ", name)
    return name if name else "sin_titulo"


def get_toc_at_level(toc: List[List], level: int) -> List[Tuple[int, str, int]]:
    return [(lvl, title, page) for (lvl, title, page, *_) in toc if lvl == level]


def end_page_for_entry(toc: List[List], idx: int, chosen_level: int, total_pages: int) -> int:
    """
    Devuelve la página final (exclusiva) para el marcador toc[idx]:
    - Corta en el siguiente marcador con nivel <= chosen_level
    - Si no hay siguiente, devuelve el final del documento (exclusivo)
    Nota: ToC es 1-based, doc es 0-based.
    """
    for j in range(idx + 1, len(toc)):
        lvl_j, _, page_j_1based, *_ = toc[j]
        if lvl_j <= chosen_level:
            return max(0, page_j_1based - 1)
    return total_pages  # exclusivo


st.set_page_config(page_title="Dividir PDF por marcadores", page_icon="📑")

st.title("📑 Dividir PDF por marcadores")
st.caption("Sube un PDF con marcadores y genera archivos por cada marcador del nivel elegido.")

# --- CSS para cambiar el texto del botón del file_uploader a "Subir archivo" ---
st.markdown(
    """
    <style>
    /* Oculta el texto original del botón y coloca "Subir archivo" */
    .stFileUploader label div div span { display: none !important; }
    .stFileUploader label div div::after { content: "Subir archivo"; }
    </style>
    """,
    unsafe_allow_html=True
)

# El label también lo dejamos en español
uploaded_file = st.file_uploader("Selecciona un PDF", type=["pdf"])

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    toc = doc.get_toc(simple=False)  # lista de [level, title, page, ...]
    total_pages = len(doc)

    if not toc:
        st.error("Este PDF no tiene marcadores.")
        st.stop()

    levels = sorted(set(item[0] for item in toc))
    level = st.selectbox("Nivel de marcador a usar", options=levels, index=0)

    selected_level_entries = get_toc_at_level(toc, level)
    st.subheader("Vista previa de secciones")
    st.write(f"Se encontraron **{len(selected_level_entries)}** marcadores en el nivel **{level}**.")

    with st.expander("Ver lista de marcadores"):
        for (_, title, page) in selected_level_entries:
            st.write(f"- pág. {page}: {title}")

    st.markdown("---")
    st.subheader("Generar archivos")
    if st.button("Dividir y descargar"):
        zip_buffer = io.BytesIO()
        name_counts = {}

        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i, item in enumerate(toc):
                lvl, title, page_1based, *_ = item
                if lvl != level:
                    continue

                start_0 = max(0, page_1based - 1)
                end_exclusive_0 = end_page_for_entry(toc, i, level, total_pages)

                out = fitz.open()
                out.insert_pdf(doc, from_page=start_0, to_page=end_exclusive_0 - 1)

                base = sanitize_filename(title)
                count = name_counts.get(base, 0)
                name_counts[base] = count + 1
                filename = base if count == 0 else f"{base} ({count})"
                filename = f"{filename}.pdf"

                zf.writestr(filename, out.tobytes())
                out.close()

        doc.close()
        zip_buffer.seek(0)
        st.download_button(
            label="⬇️ Descargar ZIP",
            data=zip_buffer,
            file_name=f"{uploaded_file.name.rsplit('.',1)[0]}_por_marcadores_nivel_{level}.zip",
            mime="application/zip",
        )
else:
    st.info("Sube un PDF para comenzar.")
