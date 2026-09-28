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
)


# ============================================================
# ESTILO
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background:
            radial-gradient(
                circle at top,
                #1c1028 0%,
                #09070d 45%,
                #020203 100%
            );
    }

    .block-container {
        max-width: 1100px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    h1 {
        text-align: center;
        color: white !important;
        font-family: Georgia, serif;
        letter-spacing: 5px;
        text-shadow:
            0 0 10px #8f45d8,
            0 0 30px #4d087d;
    }

    h2, h3 {
        color: #b978ff !important;
    }

    .seccion {
        color: #b978ff;
        font-size: 23px;
        font-weight: bold;
        letter-spacing: 2px;
        margin-top: 25px;
        margin-bottom: 12px;
    }

    .panel {
        background: rgba(14, 12, 21, 0.90);
        border: 1px solid #30263d;
        border-radius: 16px;
        padding: 22px;
        margin-bottom: 20px;
    }

    .info {
        color: #8c8b99;
        font-size: 12px;
        font-family: monospace;
        line-height: 1.6;
    }

    .stButton > button {
        min-height: 55px;
        border-radius: 16px;
        font-weight: bold;
        font-size: 16px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# FUNCIONES BÁSICAS
# ============================================================

def buscar_programa(nombre):
    return shutil.which(nombre)


def limpiar_texto(texto):
    """
    Limpia el texto antes de enviarlo a Edge TTS.

    No elimina acentos ni palabras.
    Evita que símbolos innecesarios afecten
    la narración.
    """

    texto = texto.strip()

    # URLs
    texto = re.sub(
        r"https?://\S+",
        "",
        texto,
        flags=re.IGNORECASE
    )

    # Etiquetas tipo:
    # [RISAS]
    # [GRITO]
    # [EFECTO]
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

    # Espacios repetidos
    texto = re.sub(
        r"[ \t]+",
        " ",
        texto
    )

    # Demasiados saltos
    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto
    )

    return texto.strip()


def convertir_tiempo(valor):
    """
    Convierte:

    1:54
    01:54
    00:01:54

    a segundos.
    """

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
        pass

    return 0


def obtener_duracion(archivo):
    """
    Obtiene la duración del audio con ffprobe.
    """

    ffprobe = buscar_programa(
        "ffprobe"
    )

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
                archivo,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        return float(
            resultado.stdout.strip()
        )

    except Exception:
        return 0


# ============================================================
# GENERACIÓN DE VOZ
# BASADA EN HASTAAQUI LLEGASTE
# ============================================================

def generar_voz(
    texto,
    velocidad,
    profundidad,
    reverb
):
    """
    Genera la voz utilizando:

        Edge TTS
        es-MX-JorgeNeural
        FFmpeg

    La técnica de profundidad conserva la duración
    mediante atempo.
    """

    edge_tts = buscar_programa(
        "edge-tts"
    )

    ffmpeg = buscar_programa(
        "ffmpeg"
    )

    if not edge_tts:

        return (
            None,
            "No se encontró edge-tts. "
            "Verifica requirements.txt."
        )

    if not ffmpeg:

        return (
            None,
            "No se encontró FFmpeg. "
            "Verifica packages.txt."
        )

    texto = limpiar_texto(
        texto
    )

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
        # ====================================================

        comando_tts = [
            edge_tts,

            "--voice",
            "es-MX-JorgeNeural",

            "--rate",
            rate,

            "--volume",
            "-3%",

            "--pitch",
            "0Hz",

            "--text",
            texto,

            "--write-media",
            original,
        ]

        resultado = subprocess.run(
            comando_tts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180,
        )

        if resultado.returncode != 0:

            detalle = (
                resultado.stderr
                or resultado.stdout
                or "Sin información."
            )

            return (
                None,
                "Edge TTS no pudo generar la voz:\n\n"
                + detalle[:2000]
            )

        if (
            not os.path.exists(original)
            or os.path.getsize(original) < 1000
        ):

            return (
                None,
                "Edge TTS terminó pero no generó "
                "un MP3 válido."
            )

        # ====================================================
        # PROFUNDIDAD
        # ====================================================
        #
        # 1.00 = normal
        # 0.95 = ligeramente grave
        # 0.90 = grave
        # 0.82 = muy grave
        # 0.75 = extremadamente grave
        #
        # Esto está basado en el procesamiento original
        # de HastaAquíLlegaste:
        #
        # asetrate
        # aresample
        # atempo
        #
        # De esta forma el cambio de tono no cambia
        # la duración de la narración.
        #
        # ====================================================

        factor = profundidad

        atempo = 1.0 / factor

        # ====================================================
        # REVERB
        # ====================================================

        if reverb <= 0:

            filtro_reverb = ""

        else:

            cantidad = reverb / 100.0

            d1 = int(
                50 + cantidad * 40
            )

            d2 = int(
                100 + cantidad * 60
            )

            d3 = int(
                170 + cantidad * 80
            )

            e1 = 0.18 * cantidad
            e2 = 0.13 * cantidad
            e3 = 0.08 * cantidad

            filtro_reverb = (
                f",aecho="
                f"0.80:0.72:"
                f"{d1}|{d2}|{d3}:"
                f"{e1:.3f}|"
                f"{e2:.3f}|"
                f"{e3:.3f}"
            )

        # ====================================================
        # FILTRO FINAL
        # ====================================================

        filtro = (
            f"asetrate=44100*{factor:.4f},"
            "aresample=44100,"
            f"atempo={atempo:.6f},"
            "lowpass=f=520"
            f"{filtro_reverb},"
            "alimiter=limit=0.88"
        )

        # ====================================================
        # FFMPEG
        # ====================================================

        comando_ffmpeg = [
            ffmpeg,

            "-y",

            "-loglevel",
            "error",

            "-i",
            original,

            "-af",
            filtro,

            "-ac",
            "1",

            "-ar",
            "44100",

            "-c:a",
            "pcm_s16le",

            procesada,
        ]

        resultado = subprocess.run(
            comando_ffmpeg,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180,
        )

        if resultado.returncode != 0:

            return (
                None,
                "FFmpeg no pudo procesar la voz:\n\n"
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
                "FFmpeg terminó pero no generó "
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
            "La generación de voz tardó demasiado."
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
# MEZCLAR NARRACIÓN + AMBIENTE + EFECTOS
# ============================================================

def mezclar_audio(
    voz_bytes,
    ambiente,
    efectos
):
    """
    Mezcla:

        Narración
        +
        Ambiente
        +
        múltiples efectos

    Cada efecto tiene su propio tiempo.
    """

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
        # GUARDAR VOZ
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

        # ====================================================
        # INPUTS
        # ====================================================

        inputs = [
            "-i",
            voz_path
        ]

        filtros = []

        # Voz principal
        filtros.append(
            "[0:a]volume=1.0[voz]"
        )

        siguiente = 1

        # ====================================================
        # AMBIENTE
        # ====================================================

        if ambiente is not None:

            ambiente_ext = Path(
                ambiente.name
            ).suffix or ".mp3"

            ambiente_path = os.path.join(
                carpeta,
                "ambiente" + ambiente_ext
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
                    ambiente_path,
                ]
            )

            # Volumen deliberadamente bajo
            # para que no tape la voz.
            filtros.append(
                f"[{siguiente}:a]"
                f"volume=0.18,"
                f"atrim=duration={duracion},"
                "asetpts=PTS-STARTPTS"
                "[ambiente]"
            )

            siguiente += 1

            ambiente_activo = True

        else:

            ambiente_activo = False

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
                f"efecto_{numero}{extension}"
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

            # adelay coloca el efecto exactamente
            # en el segundo indicado.
            filtros.append(
                f"[{siguiente}:a]"
                f"adelay="
                f"{int(tiempo * 1000)}:"
                f"all=1,"
                f"volume={volumen:.3f}"
                f"[{etiqueta}]"
            )

            etiquetas_efectos.append(
                f"[{etiqueta}]"
            )

            siguiente += 1

        # ====================================================
        # CREAR LISTA DE MEZCLA
        # ====================================================

        entradas_mezcla = [
            "[voz]"
        ]

        if ambiente_activo:

            entradas_mezcla.append(
                "[ambiente]"
            )

        entradas_mezcla.extend(
            etiquetas_efectos
        )

        cantidad = len(
            entradas_mezcla
        )

        filtros.append(
            "".join(
                entradas_mezcla
            )
            + f"amix=inputs={cantidad}:"
            "duration=first:"
            "dropout_transition=0,"
            "alimiter=limit=0.92"
            "[mix]"
        )

        filtro_complex = ";".join(
            filtros
        )

        # ====================================================
        # WAV FINAL
        # ====================================================

        wav_final = os.path.join(
            carpeta,
            "narracion_final.wav"
        )

        comando_wav = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
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

                wav_final,
            ]
        )

        resultado = subprocess.run(
            comando_wav,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
        )

        if resultado.returncode != 0:

            return (
                None,
                None,
                "Error creando WAV:\n\n"
                + resultado.stderr
            )

        # ====================================================
        # MP3 FINAL
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

            mp3_final,
        ]

        resultado = subprocess.run(
            comando_mp3,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
        )

        if resultado.returncode != 0:

            return (
                None,
                None,
                "Error creando MP3:\n\n"
                + resultado.stderr
            )

        # ====================================================
        # LEER RESULTADOS
        # ====================================================

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
# SESSION STATE
# ============================================================

if "resultado_wav" not in st.session_state:
    st.session_state.resultado_wav = None

if "resultado_mp3" not in st.session_state:
    st.session_state.resultado_mp3 = None

if "error" not in st.session_state:
    st.session_state.error = None


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
        margin-bottom:30px;
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
    "Texto:",
    height=320,
    placeholder=(
        "Escribe aquí tu historia...\n\n"
        "De repente se escucharon unas risas "
        "provenientes del pasillo..."
    ),
)


# ============================================================
# VOZ
# ============================================================

st.markdown(
    '<div class="seccion">🎙️ VOZ</div>',
    unsafe_allow_html=True
)

st.info(
    "Motor de voz: Edge TTS • "
    "Voz: es-MX-JorgeNeural"
)


col1, col2 = st.columns(2)


with col1:

    velocidad = st.slider(
        "⏱️ Velocidad",
        min_value=0.70,
        max_value=1.20,
        value=0.90,
        step=0.01,
        help=(
            "0.70 = lenta | "
            "1.00 = normal | "
            "1.20 = rápida"
        )
    )


with col2:

    profundidad = st.slider(
        "🐺 Profundidad / voz gruesa",
        min_value=0.70,
        max_value=1.00,
        value=0.82,
        step=0.01,
        help=(
            "1.00 = normal. "
            "0.70 = extremadamente grave."
        )
    )


reverb = st.slider(
    "🌫️ Reverberación",
    min_value=0,
    max_value=100,
    value=18,
    step=1,
)


st.markdown(
    f"""
    <div class="info">
    Velocidad: {velocidad:.2f}x<br>
    Profundidad: {profundidad:.2f}<br>
    Reverberación: {reverb}%
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
    "Carga un audio ambiental",
    type=[
        "mp3",
        "wav",
        "m4a",
        "ogg",
        "flac"
    ],
    key="ambiente"
)

if ambiente:

    st.audio(
        ambiente
    )


# ============================================================
# EFECTOS
# ============================================================

st.markdown(
    '<div class="seccion">🔊 EFECTOS DE SONIDO</div>',
    unsafe_allow_html=True
)

st.info(
    "Puedes colocar hasta 10 efectos. "
    "Ejemplo: risas en 01:54, un grito en 02:17 "
    "y una puerta en 02:43."
)


cantidad_efectos = st.number_input(
    "Cantidad de efectos",
    min_value=0,
    max_value=10,
    value=5,
    step=1
)


efectos = []


for i in range(
    int(cantidad_efectos)
):

    st.markdown(
        f"#### 🔊 Efecto {i + 1}"
    )

    col1, col2, col3 = st.columns(
        [2.2, 1, 1]
    )

    with col1:

        archivo = st.file_uploader(
            "Archivo",
            type=[
                "mp3",
                "wav",
                "m4a",
                "ogg",
                "flac"
            ],
            key=f"efecto_archivo_{i}"
        )

    with col2:

        tiempo = st.text_input(
            "Tiempo",
            value="00:00",
            placeholder="01:54",
            key=f"efecto_tiempo_{i}"
        )

    with col3:

        volumen = st.slider(
            "Volumen",
            min_value=0.0,
            max_value=1.5,
            value=0.8,
            step=0.05,
            key=f"efecto_volumen_{i}"
        )

    if archivo:

        efectos.append(
            {
                "archivo": archivo,
                "tiempo": convertir_tiempo(
                    tiempo
                ),
                "volumen": volumen,
            }
        )


# ============================================================
# GENERAR
# ============================================================

st.markdown("---")


generar = st.button(
    "🎙️ GENERAR NARRACIÓN",
    type="primary",
    use_container_width=True,
)


# ============================================================
# PROCESAMIENTO
# ============================================================

if generar:

    st.session_state.resultado_wav = None
    st.session_state.resultado_mp3 = None
    st.session_state.error = None

    if not texto.strip():

        st.error(
            "Escribe primero el texto de la narración."
        )

    else:

        # ----------------------------------------------------
        # GENERAR VOZ
        # ----------------------------------------------------

        with st.spinner(
            "🎙️ Generando voz..."
        ):

            voz, error = generar_voz(
                texto=texto,
                velocidad=velocidad,
                profundidad=profundidad,
                reverb=reverb,
            )

        if error:

            st.session_state.error = error

        else:

            # ------------------------------------------------
            # MEZCLAR
            # ------------------------------------------------

            with st.spinner(
                "🎚️ Mezclando ambiente y efectos..."
            ):

                wav, mp3, error = mezclar_audio(
                    voz_bytes=voz,
                    ambiente=ambiente,
                    efectos=efectos,
                )

            if error:

                st.session_state.error = error

            else:

                st.session_state.resultado_wav = wav
                st.session_state.resultado_mp3 = mp3


# ============================================================
# MOSTRAR ERROR
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

    # Reproductor
    st.audio(
        st.session_state.resultado_mp3,
        format="audio/mpeg"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.download_button(
            "⬇️ DESCARGAR MP3",
            data=st.session_state.resultado_mp3,
            file_name="narracion_final.mp3",
            mime="audio/mpeg",
            use_container_width=True,
        )

    with col2:

        st.download_button(
            "⬇️ DESCARGAR WAV",
            data=st.session_state.resultado_wav,
            file_name="narracion_final.wav",
            mime="audio/wav",
            use_container_width=True,
        )

    st.success(
        "🎙️ Narración generada correctamente."
    )
