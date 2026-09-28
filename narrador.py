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
# FFMPEG
# ============================================================

def buscar_ffmpeg():

    return shutil.which("ffmpeg")


# ============================================================
# LIMPIAR TEXTO
# ============================================================

def limpiar_texto(texto):

    texto = texto.strip()

    texto = re.sub(
        r"https?://\S+",
        "",
        texto,
        flags=re.IGNORECASE
    )

    texto = re.sub(
        r"\[[^\]]*\]",
        "",
        texto
    )

    texto = texto.replace('"', "")
    texto = texto.replace("“", "")
    texto = texto.replace("”", "")
    texto = texto.replace("«", "")
    texto = texto.replace("»", "")

    texto = texto.replace("—", " ")
    texto = texto.replace("–", " ")

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
# CONVERTIR TIEMPO
# ============================================================

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


# ============================================================
# FORMATEAR TIEMPO
# ============================================================

def formatear_tiempo(segundos):

    segundos = max(
        0,
        float(segundos)
    )

    horas = int(
        segundos // 3600
    )

    minutos = int(
        (segundos % 3600) // 60
    )

    secs = int(
        segundos % 60
    )

    if horas > 0:

        return (
            f"{horas:02d}:"
            f"{minutos:02d}:"
            f"{secs:02d}"
        )

    return (
        f"{minutos:02d}:"
        f"{secs:02d}"
    )


# ============================================================
# GENERAR EDGE TTS
# ============================================================

async def _generar_edge_tts(
    texto,
    archivo_salida,
    velocidad
):

    porcentaje = round(
        (velocidad - 1.0) * 100
    )

    if porcentaje >= 0:

        rate = (
            f"+{porcentaje}%"
        )

    else:

        rate = (
            f"{porcentaje}%"
        )

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
# MP3 -> WAV
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
# NO UTILIZAMOS ASETRATE
#
# LIBROSA MODIFICA EL TONO SIN MODIFICAR
# LA DURACIÓN DEL AUDIO.
# ============================================================

def cambiar_profundidad_voz(
    archivo_entrada,
    archivo_salida,
    profundidad
):

    profundidad = max(
        0,
        min(
            100,
            int(profundidad)
        )
    )

    # 0% = 0 semitonos
    # 100% = -8 semitonos

    semitonos = -(
        profundidad / 100.0
    ) * 8.0

    audio, sr = librosa.load(
        archivo_entrada,
        sr=44100,
        mono=True
    )

    if profundidad == 0:

        sf.write(
            archivo_salida,
            audio,
            sr,
            subtype="PCM_16"
        )

        return

    audio_procesado = (
        librosa.effects.pitch_shift(
            audio,
            sr=sr,
            n_steps=semitonos,
            bins_per_octave=12
        )
    )

    maximo = np.max(
        np.abs(
            audio_procesado
        )
    )

    if maximo > 0.98:

        audio_procesado *= (
            0.98 / maximo
        )

    sf.write(
        archivo_salida,
        audio_procesado,
        sr,
        subtype="PCM_16"
    )


# ============================================================
# GENERAR VOZ COMPLETA
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
            None,
            "No se encontró FFmpeg."
        )

    texto = limpiar_texto(
        texto
    )

    if not texto:

        return (
            None,
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
        # CONVERTIR
        # ====================================================

        convertir_a_wav(
            edge_mp3,
            original_wav,
            ffmpeg
        )

        # ====================================================
        # PROFUNDIDAD
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
                0.10 * cantidad
            )

            decay2 = (
                0.07 * cantidad
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
        # OBTENER DURACIÓN REAL
        # ====================================================

        duracion = obtener_duracion(
            voz_wav,
            ffmpeg
        )

        with open(
            voz_wav,
            "rb"
        ) as archivo:

            audio = archivo.read()

        return (
            audio,
            duracion,
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
# DURACIÓN REAL DEL AUDIO
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
        r"Duration:\s*"
        r"(\d+):(\d+):(\d+)\.(\d+)",
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

    fraccion = int(
        encontrado.group(4)
    )

    # FFmpeg normalmente usa centésimas
    # o milésimas dependiendo del formato.

    return (
        horas * 3600
        + minutos * 60
        + segundos
        + fraccion / 100.0
    )


# ============================================================
# MEZCLAR NARRACIÓN
# + AMBIENTE
# + EFECTOS
# + EFECTO FINAL
# ============================================================

def mezclar_audio(
    voz_bytes,
    duracion_voz,
    ambiente,
    volumen_ambiente,
    efectos,
    efecto_final,
    retraso_final,
    volumen_final
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

        # ====================================================
        # DURACIÓN TOTAL
        #
        # La duración final depende del efecto final.
        # ====================================================

        duracion_final_audio = (
            duracion_voz
        )

        if efecto_final:

            efecto_final_temp = os.path.join(
                carpeta,
                "efecto_final_temp"
                + Path(
                    efecto_final.name
                ).suffix
            )

            with open(
                efecto_final_temp,
                "wb"
            ) as archivo:

                archivo.write(
                    efecto_final.getvalue()
                )

            duracion_audio_final = (
                obtener_duracion(
                    efecto_final_temp,
                    ffmpeg
                )
            )

            duracion_final_audio = max(
                duracion_final_audio,
                duracion_voz
                + retraso_final
                + duracion_audio_final
            )

        # ====================================================
        # INPUT PRINCIPAL
        # ====================================================

        inputs = [
            "-i",
            voz_path
        ]

        filtros = []

        entradas_mix = []

        # ====================================================
        # VOZ
        # ====================================================

        filtros.append(
            "[0:a]"
            "volume=1.0"
            "[voz]"
        )

        entradas_mix.append(
            "[voz]"
        )

        siguiente = 1

        # ====================================================
        # AMBIENTE
        #
        # IMPORTANTE:
        # Se repite hasta el final del audio completo.
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
                f"atrim="
                f"duration={duracion_final_audio},"
                "asetpts=PTS-STARTPTS"
                "[ambiente]"
            )

            entradas_mix.append(
                "[ambiente]"
            )

            siguiente += 1

        # ====================================================
        # EFECTOS DURANTE LA NARRACIÓN
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
        # EFECTO FINAL
        #
        # AQUÍ ESTÁ LA NUEVA FUNCIÓN
        #
        # La narración termina.
        #
        # Esperamos X segundos.
        #
        # Luego entra la risa/sonido.
        # ====================================================

        if efecto_final:

            extension = (
                Path(
                    efecto_final.name
                ).suffix
                or ".mp3"
            )

            efecto_final_path = os.path.join(
                carpeta,
                "efecto_final" + extension
            )

            with open(
                efecto_final_path,
                "wb"
            ) as archivo:

                archivo.write(
                    efecto_final.getvalue()
                )

            milisegundos_final = int(
                (
                    duracion_voz
                    + retraso_final
                )
                * 1000
            )

            etiqueta_final = (
                "efecto_final"
            )

            # -----------------------------------------------
            # El audio final entra exactamente después
            # de terminar la voz + el retraso seleccionado.
            # -----------------------------------------------

            inputs.extend(
                [
                    "-i",
                    efecto_final_path
                ]
            )

            filtros.append(
                f"[{siguiente}:a]"
                f"adelay="
                f"{milisegundos_final}:all=1,"
                f"volume={volumen_final:.3f}"
                f"[{etiqueta_final}]"
            )

            entradas_mix.append(
                f"[{etiqueta_final}]"
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
            "duration=longest:"
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
    ) < 10:

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

if ambiente:

    st.audio(
        ambiente
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


# ============================================================
# EFECTOS DURANTE LA NARRACIÓN
# ============================================================

st.markdown(
    '<div class="seccion">🔊 EFECTOS DURANTE LA NARRACIÓN</div>',
    unsafe_allow_html=True
)

if st.button(
    "＋ Agregar efecto"
):

    agregar_efecto()

    st.rerun()


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
# EFECTO FINAL
# ============================================================

st.markdown(
    '<div class="seccion">🎬 EFECTO FINAL</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="info">
        Este efecto se colocará después de que termine
        completamente la narración.
        Puedes usarlo para risas, gritos, golpes,
        susurros, puertas, sonidos ambientales, etc.
    </div>
    """,
    unsafe_allow_html=True
)

efecto_final = st.file_uploader(
    "Audio final",
    type=[
        "mp3",
        "wav",
        "m4a",
        "ogg",
        "flac"
    ],
    key="efecto_final",
    label_visibility="collapsed"
)

col1, col2 = st.columns(2)

with col1:

    retraso_final = st.number_input(
        "⏱️ Esperar después de la narración",
        min_value=0.0,
        max_value=30.0,
        value=0.5,
        step=0.1
    )

with col2:

    volumen_final = st.slider(
        "🔊 Volumen del efecto final",
        min_value=0,
        max_value=100,
        value=80,
        step=1,
        format="%d%%"
    )

if efecto_final:

    st.audio(
        efecto_final
    )

    st.markdown(
        f"""
        <div class="info">
            El efecto entrará
            {retraso_final:.1f} segundos después
            de terminar la voz.
            &nbsp;&nbsp;|&nbsp;&nbsp;
            Volumen: {volumen_final}%
        </div>
        """,
        unsafe_allow_html=True
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

        # ====================================================
        # PREPARAR EFECTOS
        # ====================================================

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

            voz, duracion_voz, error = (
                generar_voz(
                    texto=texto,
                    velocidad=velocidad,
                    profundidad=profundidad,
                    reverb=reverb
                )
            )

        if error:

            st.session_state.error = error

        else:

            # =================================================
            # INFORMACIÓN
            # =================================================

            st.info(
                "🎙️ Narración generada: "
                + formatear_tiempo(
                    duracion_voz
                )
            )

            # =================================================
            # MEZCLAR
            # =================================================

            with st.spinner(
                "🎚️ Mezclando narración, ambiente y efectos..."
            ):

                wav, mp3, error = mezclar_audio(
                    voz_bytes=voz,
                    duracion_voz=duracion_voz,
                    ambiente=ambiente,
                    volumen_ambiente=(
                        volumen_ambiente / 100
                    ),
                    efectos=efectos_validos,
                    efecto_final=efecto_final,
                    retraso_final=retraso_final,
                    volumen_final=(
                        volumen_final / 100
                    )
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
