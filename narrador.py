import streamlit as st
import subprocess
import tempfile
import shutil
import os
import re
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Narrador",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# ESTILOS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 1050px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }

    .stApp {
        background:
            radial-gradient(
                circle at top,
                #1a0d25 0%,
                #09070d 42%,
                #030204 100%
            );
    }

    h1 {
        text-align: center;
        color: #ffffff !important;
        font-family: Georgia, serif;
        font-size: 34px !important;
        letter-spacing: 4px;
        margin-bottom: 0.2rem;
        text-shadow:
            0 0 8px #8f45d8,
            0 0 22px #4d087d;
    }

    .seccion {
        color: #b978ff;
        font-size: 17px;
        font-weight: 700;
        letter-spacing: 1.5px;
        margin-top: 18px;
        margin-bottom: 7px;
    }

    .info {
        color: #858391;
        font-size: 11px;
        font-family: monospace;
        line-height: 1.5;
    }

    .stButton > button {
        min-height: 38px !important;
        height: 38px !important;
        padding: 4px 12px !important;
        border-radius: 10px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
    }

    div.stButton > button[kind="primary"] {
        min-height: 46px !important;
        height: 46px !important;
        font-size: 15px !important;
        border-radius: 12px !important;
    }

    .stTextInput input {
        min-height: 36px !important;
        height: 36px !important;
        font-size: 13px !important;
    }

    .stTextArea textarea {
        font-size: 14px !important;
        line-height: 1.55 !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SESSION STATE
# ============================================================

if "resultado_wav" not in st.session_state:
    st.session_state.resultado_wav = None

if "resultado_mp3" not in st.session_state:
    st.session_state.resultado_mp3 = None

if "error" not in st.session_state:
    st.session_state.error = None

if "efectos" not in st.session_state:
    st.session_state.efectos = []


# ============================================================
# UTILIDADES
# ============================================================

def buscar_programa(nombre):
    return shutil.which(nombre)


def limpiar_texto(texto):

    texto = texto.strip()

    # Eliminar URLs
    texto = re.sub(
        r"https?://\S+",
        "",
        texto,
        flags=re.IGNORECASE
    )

    # Eliminar contenido entre corchetes
    texto = re.sub(
        r"\[[^\]]*\]",
        "",
        texto
    )

    # Guiones largos
    texto = texto.replace("—", " ")
    texto = texto.replace("–", " ")

    # Comillas
    texto = texto.replace('"', "")
    texto = texto.replace("“", "")
    texto = texto.replace("”", "")
    texto = texto.replace("«", "")
    texto = texto.replace("»", "")

    # Evitar demasiados saltos
    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto
    )

    # Espacios
    texto = re.sub(
        r"[ \t]+",
        " ",
        texto
    )

    return texto.strip()


def convertir_tiempo(valor):

    try:

        valor = str(valor).strip()

        if not valor:
            return 0

        partes = valor.split(":")

        if len(partes) == 1:
            return float(partes[0])

        if len(partes) == 2:

            minutos = int(partes[0])
            segundos = int(partes[1])

            segundos = max(
                0,
                min(
                    59,
                    segundos
                )
            )

            return (
                minutos * 60
                + segundos
            )

        if len(partes) == 3:

            horas = int(partes[0])
            minutos = int(partes[1])
            segundos = int(partes[2])

            return (
                horas * 3600
                + minutos * 60
                + segundos
            )

    except Exception:
        return 0

    return 0


def obtener_duracion(archivo):

    ffprobe = buscar_programa("ffprobe")

    if not ffprobe:
        return 0

    try:

        resultado = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                archivo
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        return float(
            resultado.stdout.strip()
        )

    except Exception:
        return 0


# ============================================================
# GENERAR VOZ
# ============================================================

def generar_voz(
    texto,
    velocidad,
    profundidad,
    reverb
):

    edge_tts = buscar_programa("edge-tts")
    ffmpeg = buscar_programa("ffmpeg")

    if not edge_tts:
        return (
            None,
            "No se encontró edge-tts."
        )

    if not ffmpeg:
        return (
            None,
            "No se encontró FFmpeg."
        )

    texto = limpiar_texto(texto)

    if not texto:
        return (
            None,
            "El texto está vacío."
        )

    carpeta = tempfile.mkdtemp(
        prefix="narrador_tts_"
    )

    original = os.path.join(
        carpeta,
        "voz_original.mp3"
    )

    procesada = os.path.join(
        carpeta,
        "voz_procesada.wav"
    )

    try:

        # ====================================================
        # VELOCIDAD
        # ====================================================

        porcentaje = int(
            (velocidad - 1.0) * 100
        )

        if porcentaje >= 0:
            rate = f"+{porcentaje}%"
        else:
            rate = f"{porcentaje}%"

        # ====================================================
        # EDGE TTS
        #
        # NO usamos --pitch.
        #
        # El pitch se procesa posteriormente.
        # ====================================================

        comando_tts = [
            edge_tts,
            "--voice",
            "es-MX-JorgeNeural",
            "--rate",
            rate,
            "--volume",
            "+0%",
            "--text",
            texto,
            "--write-media",
            original
        ]

        resultado = subprocess.run(
            comando_tts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180
        )

        if resultado.returncode != 0:

            return (
                None,
                "Edge TTS no pudo generar "
                "la voz:\n\n"
                + (
                    resultado.stderr
                    or resultado.stdout
                    or "Sin información."
                )
            )

        if (
            not os.path.exists(original)
            or os.path.getsize(original) < 1000
        ):

            return (
                None,
                "Edge TTS no generó un audio válido."
            )

        # ====================================================
        # PROFUNDIDAD
        #
        # 0%   = original
        # 25%  = ligeramente grave
        # 50%  = grave
        # 75%  = muy grave
        # 100% = máximo
        #
        # IMPORTANTE:
        # El slider va de izquierda a derecha:
        #
        # 0 ------------------------------ 100
        # normal                         grave
        # ====================================================

        profundidad = max(
            0,
            min(
                100,
                int(profundidad)
            )
        )

        # Factor de tono.
        #
        # 0%   -> 1.00
        # 100% -> 0.70
        #
        # Cuanto menor el factor,
        # más grave.

        factor_pitch = (
            1.0
            - (
                profundidad / 100.0
            ) * 0.30
        )

        # ====================================================
        # FILTROS
        # ====================================================

        filtros = []

        # ----------------------------------------------------
        # TONO
        # ----------------------------------------------------
        #
        # IMPORTANTE:
        #
        # No utilizamos --pitch de Edge TTS.
        #
        # Esto evita el error:
        #
        # Invalid pitch '0Hz'
        #
        # y permite tener el control desde 0 a 100%.
        #
        # ====================================================

        filtros.append(
            f"asetrate="
            f"44100*{factor_pitch:.4f},"
            f"aresample=44100"
        )

        # ----------------------------------------------------
        # COMPRESOR
        # ----------------------------------------------------

        filtros.append(
            "acompressor="
            "threshold=-18dB:"
            "ratio=2.5:"
            "attack=15:"
            "release=120"
        )

        # ----------------------------------------------------
        # EQ GRAVE
        # ----------------------------------------------------

        if profundidad > 0:

            ganancia_grave = (
                profundidad * 0.04
            )

            filtros.append(
                "equalizer="
                "f=120:"
                "t=q:"
                "w=1.0:"
                f"g={ganancia_grave:.2f}"
            )

        # ----------------------------------------------------
        # PRESENCIA
        # ----------------------------------------------------

        filtros.append(
            "equalizer="
            "f=3000:"
            "t=q:"
            "w=1.2:"
            "g=1"
        )

        # ----------------------------------------------------
        # REVERB
        # ----------------------------------------------------

        if reverb > 0:

            cantidad = (
                float(reverb)
                / 100.0
            )

            delay1 = int(
                45 + cantidad * 35
            )

            delay2 = int(
                90 + cantidad * 50
            )

            delay3 = int(
                150 + cantidad * 70
            )

            echo1 = 0.10 * cantidad
            echo2 = 0.07 * cantidad
            echo3 = 0.04 * cantidad

            filtros.append(
                f"aecho="
                f"0.85:0.65:"
                f"{delay1}|"
                f"{delay2}|"
                f"{delay3}:"
                f"{echo1:.3f}|"
                f"{echo2:.3f}|"
                f"{echo3:.3f}"
            )

        # ----------------------------------------------------
        # LIMITADOR
        # ----------------------------------------------------

        filtros.append(
            "alimiter="
            "limit=0.90"
        )

        filtro_final = ",".join(
            filtros
        )

        # ====================================================
        # PROCESAMIENTO
        # ====================================================

        comando_ffmpeg = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",

            "-i",
            original,

            "-af",
            filtro_final,

            "-ar",
            "44100",

            "-ac",
            "1",

            "-c:a",
            "pcm_s16le",

            procesada
        ]

        resultado = subprocess.run(
            comando_ffmpeg,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180
        )

        if resultado.returncode != 0:

            return (
                None,
                "FFmpeg no pudo procesar "
                "la voz:\n\n"
                + (
                    resultado.stderr
                    or "Sin información."
                )
            )

        if (
            not os.path.exists(procesada)
            or os.path.getsize(procesada) < 1000
        ):

            return (
                None,
                "FFmpeg no generó "
                "un WAV válido."
            )

        with open(
            procesada,
            "rb"
        ) as archivo:

            audio = archivo.read()

        return (
            audio,
            None
        )

    except subprocess.TimeoutExpired:

        return (
            None,
            "La generación de voz "
            "tardó demasiado."
        )

    except Exception as error:

        return (
            None,
            f"{type(error).__name__}: {error}"
        )

    finally:

        shutil.rmtree(
            carpeta,
            ignore_errors=True
        )


# ============================================================
# MEZCLAR AUDIO
# ============================================================

def mezclar_audio(
    voz_bytes,
    ambiente,
    volumen_ambiente,
    efectos
):

    ffmpeg = buscar_programa(
        "ffmpeg"
    )

    if not ffmpeg:

        return (
            None,
            None,
            "No se encontró FFmpeg."
        )

    carpeta = tempfile.mkdtemp(
        prefix="narrador_mix_"
    )

    try:

        # ====================================================
        # VOZ
        # ====================================================

        voz_path = os.path.join(
            carpeta,
            "voz.wav"
        )

        with open(
            voz_path,
            "wb"
        ) as archivo:

            archivo.write(
                voz_bytes
            )

        duracion = obtener_duracion(
            voz_path
        )

        if duracion <= 0:

            return (
                None,
                None,
                "No se pudo determinar "
                "la duración de la narración."
            )

        inputs = [
            "-i",
            voz_path
        ]

        filtros = []

        # ====================================================
        # VOZ PRINCIPAL
        # ====================================================

        filtros.append(
            "[0:a]"
            "volume=1.0"
            "[voz]"
        )

        siguiente = 1

        # ====================================================
        # AMBIENTE
        # ====================================================

        ambiente_activo = False

        if ambiente is not None:

            extension = (
                Path(
                    ambiente.name
                ).suffix
                or ".mp3"
            )

            ambiente_path = os.path.join(
                carpeta,
                "ambiente"
                + extension
            )

            with open(
                ambiente_path,
                "wb"
            ) as archivo:

                archivo.write(
                    ambiente.getvalue()
                )

            inputs.extend(
                [
                    "-stream_loop",
                    "-1",
                    "-i",
                    ambiente_path
                ]
            )

            filtros.append(
                f"[{siguiente}:a]"
                f"volume="
                f"{volumen_ambiente:.3f},"
                f"atrim="
                f"duration={duracion},"
                "asetpts=PTS-STARTPTS"
                "[ambiente]"
            )

            siguiente += 1

            ambiente_activo = True

        # ====================================================
        # EFECTOS
        # ====================================================

        etiquetas_efectos = []

        for numero, efecto in enumerate(
            efectos
        ):

            archivo = efecto["archivo"]
            tiempo = efecto["tiempo"]
            volumen = efecto["volumen"]

            extension = (
                Path(
                    archivo.name
                ).suffix
                or ".mp3"
            )

            efecto_path = os.path.join(
                carpeta,
                f"efecto_{numero}"
                + extension
            )

            with open(
                efecto_path,
                "wb"
            ) as archivo_salida:

                archivo_salida.write(
                    archivo.getvalue()
                )

            inputs.extend(
                [
                    "-i",
                    efecto_path
                ]
            )

            etiqueta = (
                f"fx{numero}"
            )

            milisegundos = int(
                tiempo * 1000
            )

            filtros.append(
                f"[{siguiente}:a]"
                f"adelay="
                f"{milisegundos}:all=1,"
                f"volume="
                f"{volumen:.3f}"
                f"[{etiqueta}]"
            )

            etiquetas_efectos.append(
                f"[{etiqueta}]"
            )

            siguiente += 1

        # ====================================================
        # MEZCLA
        # ====================================================

        entradas = [
            "[voz]"
        ]

        if ambiente_activo:

            entradas.append(
                "[ambiente]"
            )

        entradas.extend(
            etiquetas_efectos
        )

        cantidad = len(
            entradas
        )

        filtros.append(
            "".join(entradas)
            + f"amix="
            f"inputs={cantidad}:"
            "duration=first:"
            "dropout_transition=0,"
            "alimiter=limit=0.92"
            "[mix]"
        )

        filtro_complex = ";".join(
            filtros
        )

        # ====================================================
        # WAV
        # ====================================================

        wav_final = os.path.join(
            carpeta,
            "narracion_final.wav"
        )

        comando_wav = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error"
        ]

        comando_wav.extend(
            inputs
        )

        comando_wav.extend(
            [
                "-filter_complex",
                filtro_complex,
                "-map",
                "[mix]",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                wav_final
            ]
        )

        resultado = subprocess.run(
            comando_wav,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300
        )

        if resultado.returncode != 0:

            return (
                None,
                None,
                "Error creando WAV:\n\n"
                + (
                    resultado.stderr
                    or "Sin información."
                )
            )

        # ====================================================
        # MP3
        # ====================================================

        mp3_final = os.path.join(
            carpeta,
            "narracion_final.mp3"
        )

        comando_mp3 = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            wav_final,
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
            mp3_final
        ]

        resultado = subprocess.run(
            comando_mp3,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300
        )

        if resultado.returncode != 0:

            return (
                None,
                None,
                "Error creando MP3:\n\n"
                + (
                    resultado.stderr
                    or "Sin información."
                )
            )

        with open(
            wav_final,
            "rb"
        ) as archivo:

            wav_bytes = archivo.read()

        with open(
            mp3_final,
            "rb"
        ) as archivo:

            mp3_bytes = archivo.read()

        return (
            wav_bytes,
            mp3_bytes,
            None
        )

    except Exception as error:

        return (
            None,
            None,
            f"{type(error).__name__}: {error}"
        )

    finally:

        shutil.rmtree(
            carpeta,
            ignore_errors=True
        )


# ============================================================
# EFECTOS DINÁMICOS
# ============================================================

def agregar_efecto():

    if len(
        st.session_state.efectos
    ) >= 10:

        return

    st.session_state.efectos.append(
        {
            "archivo": None,
            "tiempo": "00:00",
            "volumen": 0.80
        }
    )


def eliminar_efecto(indice):

    if (
        0 <= indice
        < len(
            st.session_state.efectos
        )
    ):

        st.session_state.efectos.pop(
            indice
        )


# ============================================================
# ENCABEZADO
# ============================================================

st.markdown(
    "# 🎙️ NARRADOR"
)

st.markdown(
    """
    <div style="
        text-align:center;
        color:#858391;
        font-family:monospace;
        font-size:11px;
        margin-bottom:18px;
    ">
        GENERADOR DE NARRACIONES CINEMATOGRÁFICAS
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# TEXTO
# ============================================================

st.markdown(
    '<div class="seccion">📝 NARRACIÓN</div>',
    unsafe_allow_html=True
)

texto = st.text_area(
    "Texto",
    height=240,
    placeholder=(
        "Escribe aquí la historia "
        "que quieres convertir en narración..."
    ),
    label_visibility="collapsed"
)


# ============================================================
# CONTROLES DE VOZ
# ============================================================

st.markdown(
    '<div class="seccion">🎙️ VOZ</div>',
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(
    [1, 1, 1]
)

with col1:

    velocidad = st.slider(
        "⏱️ Velocidad",
        min_value=0.70,
        max_value=1.20,
        value=0.90,
        step=0.01
    )

with col2:

    profundidad = st.slider(
        "🐺 Voz gruesa",
        min_value=0,
        max_value=100,
        value=30,
        step=1,
        format="%d%%"
    )

with col3:

    reverb = st.slider(
        "🌫️ Reverb",
        min_value=0,
        max_value=100,
        value=18,
        step=1,
        format="%d%%"
    )


st.markdown(
    f"""
    <div class="info">
        Velocidad: {velocidad:.2f}x
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Voz gruesa: {profundidad}%
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Reverb: {reverb}%
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# AMBIENTE
# ============================================================

st.markdown(
    '<div class="seccion">🌑 AMBIENTE</div>',
    unsafe_allow_html=True
)

ambiente = st.file_uploader(
    "Audio ambiental",
    type=[
        "mp3",
        "wav",
        "m4a",
        "ogg",
        "flac"
    ],
    key="ambiente",
    label_visibility="collapsed"
)

volumen_ambiente = st.slider(
    "🔊 Volumen del ambiente",
    min_value=0,
    max_value=100,
    value=20,
    step=1,
    format="%d%%"
)

volumen_ambiente_ffmpeg = (
    volumen_ambiente / 100.0
)

st.markdown(
    f"""
    <div class="info">
        Volumen ambiente: {volumen_ambiente}%
        &nbsp;&nbsp;•&nbsp;&nbsp;
        🔁 Loop automático
    </div>
    """,
    unsafe_allow_html=True
)

if ambiente:

    st.audio(
        ambiente
    )


# ============================================================
# EFECTOS
# ============================================================

st.markdown(
    '<div class="seccion">🔊 EFECTOS</div>',
    unsafe_allow_html=True
)

col1, col2 = st.columns(
    [1, 5]
)

with col1:

    if st.button(
        "＋ Efecto",
        use_container_width=True
    ):

        agregar_efecto()

        st.rerun()

with col2:

    cantidad_efectos = len(
        st.session_state.efectos
    )

    if cantidad_efectos:

        st.markdown(
            f"""
            <div class="info">
                {cantidad_efectos}
                efecto(s) agregado(s)
                • máximo 10
            </div>
            """,
            unsafe_allow_html=True
        )

    else:

        st.markdown(
            """
            <div class="info">
                Agrega efectos solamente cuando
                los necesites.
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# BLOQUES DE EFECTOS
# ============================================================

for indice, efecto in enumerate(
    st.session_state.efectos
):

    with st.container(
        border=True
    ):

        col1, col2, col3, col4 = st.columns(
            [3, 1.2, 1.2, 0.8]
        )

        with col1:

            archivo = st.file_uploader(
                "🔊 Archivo",
                type=[
                    "mp3",
                    "wav",
                    "m4a",
                    "ogg",
                    "flac"
                ],
                key=f"archivo_{indice}"
            )

            efecto["archivo"] = archivo

        with col2:

            tiempo = st.text_input(
                "⏱️ Tiempo",
                value=efecto["tiempo"],
                placeholder="01:54",
                key=f"tiempo_{indice}"
            )

            efecto["tiempo"] = tiempo

        with col3:

            volumen = st.slider(
                "🔊 Volumen",
                min_value=0.0,
                max_value=1.5,
                value=float(
                    efecto["volumen"]
                ),
                step=0.05,
                key=f"volumen_{indice}"
            )

            efecto["volumen"] = volumen

        with col4:

            st.markdown(
                "<br>",
                unsafe_allow_html=True
            )

            if st.button(
                "🗑️",
                key=f"eliminar_{indice}",
                help="Eliminar efecto"
            ):

                eliminar_efecto(
                    indice
                )

                st.rerun()

        if archivo:

            st.audio(
                archivo
            )


# ============================================================
# GENERAR NARRACIÓN
# ============================================================

st.markdown("---")

generar = st.button(
    "🎙️ GENERAR NARRACIÓN",
    type="primary",
    use_container_width=True
)


if generar:

    st.session_state.resultado_wav = None
    st.session_state.resultado_mp3 = None
    st.session_state.error = None

    if not texto.strip():

        st.error(
            "Escribe primero el texto."
        )

    else:

        efectos_validos = []

        for efecto in (
            st.session_state.efectos
        ):

            if efecto["archivo"]:

                efectos_validos.append(
                    {
                        "archivo":
                            efecto["archivo"],

                        "tiempo":
                            convertir_tiempo(
                                efecto["tiempo"]
                            ),

                        "volumen":
                            efecto["volumen"]
                    }
                )

        # ====================================================
        # GENERAR VOZ
        # ====================================================

        with st.spinner(
            "🎙️ Generando narración..."
        ):

            voz, error = generar_voz(
                texto=texto,
                velocidad=velocidad,
                profundidad=profundidad,
                reverb=reverb
            )

        if error:

            st.session_state.error = error

        else:

            # =================================================
            # MEZCLAR
            # =================================================

            with st.spinner(
                "🎚️ Mezclando voz, ambiente y efectos..."
            ):

                wav, mp3, error = mezclar_audio(
                    voz_bytes=voz,
                    ambiente=ambiente,
                    volumen_ambiente=(
                        volumen_ambiente_ffmpeg
                    ),
                    efectos=efectos_validos
                )

            if error:

                st.session_state.error = error

            else:

                st.session_state.resultado_wav = wav
                st.session_state.resultado_mp3 = mp3


# ============================================================
# ERROR
# ============================================================

if st.session_state.error:

    st.error(
        st.session_state.error
    )


# ============================================================
# RESULTADO
# ============================================================

if st.session_state.resultado_mp3:

    st.markdown("---")

    st.markdown(
        "## 🎧 NARRACIÓN FINAL"
    )

    st.audio(
        st.session_state.resultado_mp3,
        format="audio/mpeg"
    )

    col1, col2 = st.columns(
        [1, 1]
    )

    with col1:

        st.download_button(
            "⬇️ Descargar MP3",
            data=st.session_state.resultado_mp3,
            file_name="narracion_final.mp3",
            mime="audio/mpeg",
            use_container_width=True
        )

    with col2:

        st.download_button(
            "⬇️ Descargar WAV",
            data=st.session_state.resultado_wav,
            file_name="narracion_final.wav",
            mime="audio/wav",
            use_container_width=True
        )

    st.success(
        "🎙️ Narración generada correctamente."
    )
