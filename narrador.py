import streamlit as st
import subprocess
import tempfile
import shutil
import os
import re
import asyncio
from pathlib import Path

import numpy as np
import librosa
import soundfile as sf
import edge_tts


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
# ESTILO
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
        color: white !important;
        font-family: Georgia, serif;
        font-size: 34px !important;
        letter-spacing: 4px;
        margin-bottom: 4px;
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

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SESSION STATE
# ============================================================

if "efectos" not in st.session_state:
    st.session_state.efectos = []

if "resultado_mp3" not in st.session_state:
    st.session_state.resultado_mp3 = None

if "resultado_wav" not in st.session_state:
    st.session_state.resultado_wav = None

if "error" not in st.session_state:
    st.session_state.error = None


# ============================================================
# BUSCAR FFMPEG
# ============================================================

def buscar_ffmpeg():

    ffmpeg = shutil.which("ffmpeg")

    if not ffmpeg:
        return None

    return ffmpeg


# ============================================================
# LIMPIAR TEXTO
# ============================================================

def limpiar_texto(texto):

    texto = texto.strip()

    # URLs
    texto = re.sub(
        r"https?://\S+",
        "",
        texto,
        flags=re.IGNORECASE
    )

    # Corchetes
    texto = re.sub(
        r"\[[^\]]*\]",
        "",
        texto
    )

    # Comillas
    texto = texto.replace('"', "")
    texto = texto.replace("“", "")
    texto = texto.replace("”", "")
    texto = texto.replace("«", "")
    texto = texto.replace("»", "")

    # Guiones largos
    texto = texto.replace("—", " ")
    texto = texto.replace("–", " ")

    # Evitar espacios excesivos
    texto = re.sub(
        r"[ \t]+",
        " ",
        texto
    )

    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto
    )

    return texto.strip()


# ============================================================
# TIEMPO
# ============================================================

def convertir_tiempo(valor):

    try:

        valor = str(valor).strip()

        if not valor:
            return 0

        partes = valor.split(":")

        if len(partes) == 1:

            return float(
                partes[0]
            )

        if len(partes) == 2:

            minutos = int(
                partes[0]
            )

            segundos = int(
                partes[1]
            )

            return (
                minutos * 60
                + segundos
            )

        if len(partes) == 3:

            horas = int(
                partes[0]
            )

            minutos = int(
                partes[1]
            )

            segundos = int(
                partes[2]
            )

            return (
                horas * 3600
                + minutos * 60
                + segundos
            )

    except Exception:

        return 0

    return 0


# ============================================================
# GENERAR EDGE TTS
# ============================================================

async def _generar_edge_tts(
    texto,
    archivo_salida,
    velocidad
):

    # --------------------------------------------------------
    # Convertimos la velocidad de 0.70 - 1.20
    # a formato de Edge TTS.
    # --------------------------------------------------------

    porcentaje = round(
        (velocidad - 1.0) * 100
    )

    if porcentaje >= 0:
        rate = f"+{porcentaje}%"
    else:
        rate = f"{porcentaje}%"

    # --------------------------------------------------------
    # VOZ MASCULINA MEXICANA
    # --------------------------------------------------------

    communicate = edge_tts.Communicate(
        texto,
        "es-MX-JorgeNeural",
        rate=rate,
        volume="+0%"
    )

    await communicate.save(
        archivo_salida
    )


def generar_edge_tts(
    texto,
    velocidad,
    archivo_salida
):

    asyncio.run(
        _generar_edge_tts(
            texto,
            archivo_salida,
            velocidad
        )
    )


# ============================================================
# CONVERTIR MP3 DE EDGE TTS A WAV
# ============================================================

def convertir_a_wav(
    entrada,
    salida,
    ffmpeg
):

    comando = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-i",
        entrada,
        "-ar",
        "44100",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        salida
    ]

    resultado = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=180
    )

    if resultado.returncode != 0:

        raise RuntimeError(
            resultado.stderr
            or "FFmpeg no pudo convertir el audio."
        )


# ============================================================
# CAMBIO DE TONO
#
# ESTA ES LA PARTE IMPORTANTE
#
# NO usamos:
#
#     asetrate
#
# NO usamos:
#
#     --pitch
#
# Librosa pitch_shift modifica el tono
# conservando la duración.
# ============================================================

def cambiar_profundidad_voz(
    archivo_entrada,
    archivo_salida,
    profundidad
):

    # --------------------------------------------------------
    # 0% = 0 semitonos
    #
    # 100% = -8 semitonos
    #
    # Esto produce una voz bastante profunda
    # sin convertirla en una voz acelerada.
    # --------------------------------------------------------

    profundidad = max(
        0,
        min(
            100,
            int(profundidad)
        )
    )

    semitonos = -(
        profundidad / 100.0
    ) * 8.0

    # --------------------------------------------------------
    # Cargar audio
    # --------------------------------------------------------

    audio, sr = librosa.load(
        archivo_entrada,
        sr=44100,
        mono=True
    )

    # --------------------------------------------------------
    # 0% = NO procesamos.
    #
    # Esto conserva exactamente la voz original.
    # --------------------------------------------------------

    if profundidad == 0:

        sf.write(
            archivo_salida,
            audio,
            sr,
            subtype="PCM_16"
        )

        return

    # --------------------------------------------------------
    # CAMBIO DE TONO
    #
    # duration se mantiene.
    # --------------------------------------------------------

    audio_procesado = librosa.effects.pitch_shift(
        audio,
        sr=sr,
        n_steps=semitonos,
        bins_per_octave=12
    )

    # --------------------------------------------------------
    # Normalización suave
    # --------------------------------------------------------

    maximo = np.max(
        np.abs(
            audio_procesado
        )
    )

    if maximo > 0.98:

        audio_procesado = (
            audio_procesado
            * (0.98 / maximo)
        )

    # --------------------------------------------------------
    # Guardar
    # --------------------------------------------------------

    sf.write(
        archivo_salida,
        audio_procesado,
        sr,
        subtype="PCM_16"
    )


# ============================================================
# PROCESAR VOZ
# ============================================================

def generar_voz(
    texto,
    velocidad,
    profundidad,
    reverb
):

    ffmpeg = buscar_ffmpeg()

    if not ffmpeg:

        return (
            None,
            "No se encontró FFmpeg."
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
        prefix="narrador_"
    )

    try:

        edge_mp3 = os.path.join(
            carpeta,
            "edge.mp3"
        )

        original_wav = os.path.join(
            carpeta,
            "original.wav"
        )

        voz_wav = os.path.join(
            carpeta,
            "voz.wav"
        )

        # ====================================================
        # EDGE TTS
        # ====================================================

        generar_edge_tts(
            texto,
            velocidad,
            edge_mp3
        )

        if (
            not os.path.exists(edge_mp3)
            or os.path.getsize(edge_mp3) < 1000
        ):

            raise RuntimeError(
                "Edge TTS no generó un audio válido."
            )

        # ====================================================
        # MP3 -> WAV
        # ====================================================

        convertir_a_wav(
            edge_mp3,
            original_wav,
            ffmpeg
        )

        # ====================================================
        # CAMBIO DE TONO
        # ====================================================

        cambiar_profundidad_voz(
            original_wav,
            voz_wav,
            profundidad
        )

        # ====================================================
        # REVERB
        # ====================================================

        if reverb > 0:

            voz_reverb = os.path.join(
                carpeta,
                "voz_reverb.wav"
            )

            cantidad = (
                reverb / 100.0
            )

            delay1 = int(
                45 + cantidad * 30
            )

            delay2 = int(
                90 + cantidad * 45
            )

            decay1 = (
                0.10
                * cantidad
            )

            decay2 = (
                0.07
                * cantidad
            )

            filtro = (
                "aecho="
                "0.85:0.65:"
                f"{delay1}|{delay2}:"
                f"{decay1:.3f}|"
                f"{decay2:.3f}"
            )

            comando = [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                voz_wav,
                "-af",
                filtro,
                "-ar",
                "44100",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                voz_reverb
            ]

            resultado = subprocess.run(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180
            )

            if resultado.returncode != 0:

                raise RuntimeError(
                    resultado.stderr
                    or "Error aplicando reverb."
                )

            voz_wav = voz_reverb

        # ====================================================
        # LEER RESULTADO
        # ====================================================

        with open(
            voz_wav,
            "rb"
        ) as archivo:

            audio = archivo.read()

        return (
            audio,
            None
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
# DURACIÓN
# ============================================================

def obtener_duracion(
    archivo,
    ffmpeg
):

    comando = [
        ffmpeg,
        "-i",
        archivo
    ]

    resultado = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    texto = resultado.stderr

    encontrado = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)",
        texto
    )

    if not encontrado:

        return 0

    horas = int(
        encontrado.group(1)
    )

    minutos = int(
        encontrado.group(2)
    )

    segundos = int(
        encontrado.group(3)
    )

    return (
        horas * 3600
        + minutos * 60
        + segundos
    )


# ============================================================
# MEZCLAR TODO
# ============================================================

def mezclar_audio(
    voz_bytes,
    ambiente,
    volumen_ambiente,
    efectos
):

    ffmpeg = buscar_ffmpeg()

    if not ffmpeg:

        return (
            None,
            None,
            "No se encontró FFmpeg."
        )

    carpeta = tempfile.mkdtemp(
        prefix="mezcla_"
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
            voz_path,
            ffmpeg
        )

        if duracion <= 0:

            raise RuntimeError(
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

        # ====================================================
        # VOZ
        # ====================================================

        filtros.append(
            "[0:a]"
            "volume=1.0"
            "[voz]"
        )

        siguiente = 1

        entradas_mix = [
            "[voz]"
        ]

        # ====================================================
        # AMBIENTE
        # ====================================================

        if ambiente:

            extension = (
                Path(
                    ambiente.name
                ).suffix
                or ".mp3"
            )

            ambiente_path = os.path.join(
                carpeta,
                "ambiente" + extension
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
                f"volume={volumen_ambiente:.3f},"
                f"atrim=duration={duracion},"
                "asetpts=PTS-STARTPTS"
                "[ambiente]"
            )

            entradas_mix.append(
                "[ambiente]"
            )

            siguiente += 1

        # ====================================================
        # EFECTOS
        # ====================================================

        for numero, efecto in enumerate(
            efectos
        ):

            archivo = efecto["archivo"]

            if not archivo:
                continue

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

            milisegundos = int(
                tiempo * 1000
            )

            etiqueta = (
                f"fx{numero}"
            )

            inputs.extend(
                [
                    "-i",
                    efecto_path
                ]
            )

            filtros.append(
                f"[{siguiente}:a]"
                f"adelay="
                f"{milisegundos}:all=1,"
                f"volume={volumen:.3f}"
                f"[{etiqueta}]"
            )

            entradas_mix.append(
                f"[{etiqueta}]"
            )

            siguiente += 1

        # ====================================================
        # MEZCLA
        # ====================================================

        cantidad = len(
            entradas_mix
        )

        filtros.append(
            "".join(
                entradas_mix
            )
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

            raise RuntimeError(
                resultado.stderr
                or "No se pudo crear el WAV."
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

            raise RuntimeError(
                resultado.stderr
                or "No se pudo crear el MP3."
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
# AGREGAR EFECTO
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


# ============================================================
# INTERFAZ
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
    height=230,
    placeholder=(
        "Escribe aquí la historia "
        "que quieres convertir en narración..."
    ),
    label_visibility="collapsed"
)


# ============================================================
# VOZ
# ============================================================

st.markdown(
    '<div class="seccion">🎙️ VOZ</div>',
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(3)

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
        value=15,
        step=1,
        format="%d%%"
    )

st.markdown(
    f"""
    <div class="info">
        Velocidad: {velocidad:.2f}x
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Profundidad: {profundidad}%
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

st.markdown(
    f"""
    <div class="info">
        Volumen: {volumen_ambiente}%
        &nbsp;&nbsp;•&nbsp;&nbsp;
        🔁 El ambiente se repite automáticamente
        hasta terminar la narración.
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

if st.button(
    "＋ Agregar efecto"
):

    agregar_efecto()

    st.rerun()


# ============================================================
# LISTA DE EFECTOS
# ============================================================

for indice, efecto in enumerate(
    st.session_state.efectos
):

    with st.container(
        border=True
    ):

        col1, col2, col3, col4 = st.columns(
            [3, 1.2, 1.2, 0.7]
        )

        with col1:

            archivo = st.file_uploader(
                "🔊 Sonido",
                type=[
                    "mp3",
                    "wav",
                    "m4a",
                    "ogg",
                    "flac"
                ],
                key=f"efecto_archivo_{indice}"
            )

            efecto["archivo"] = archivo

        with col2:

            efecto["tiempo"] = st.text_input(
                "⏱️ Tiempo",
                value=efecto["tiempo"],
                placeholder="01:54",
                key=f"efecto_tiempo_{indice}"
            )

        with col3:

            efecto["volumen"] = st.slider(
                "🔊 Volumen",
                min_value=0.0,
                max_value=1.5,
                value=float(
                    efecto["volumen"]
                ),
                step=0.05,
                key=f"efecto_volumen_{indice}"
            )

        with col4:

            st.markdown(
                "<br>",
                unsafe_allow_html=True
            )

            if st.button(
                "🗑️",
                key=f"borrar_efecto_{indice}"
            ):

                st.session_state.efectos.pop(
                    indice
                )

                st.rerun()

        if archivo:

            st.audio(
                archivo
            )


# ============================================================
# GENERAR
# ============================================================

st.markdown("---")

generar = st.button(
    "🎙️ GENERAR NARRACIÓN",
    type="primary",
    use_container_width=True
)


if generar:

    st.session_state.resultado_mp3 = None
    st.session_state.resultado_wav = None
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
            "🎙️ Generando voz..."
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
                "🎚️ Mezclando narración..."
            ):

                wav, mp3, error = mezclar_audio(
                    voz_bytes=voz,
                    ambiente=ambiente,
                    volumen_ambiente=(
                        volumen_ambiente / 100
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

    col1, col2 = st.columns(2)

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
