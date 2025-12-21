from typing import Any, Text, Dict, List
import os
import requests

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


# Conexión directa a Ollama
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3:8b")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8001")
TB_IMAGE_API_URL = os.getenv("TB_IMAGE_API_URL", "http://tb-image-service:8001/analyze")


class ActionGuardarUltimaPregunta(Action):
    def name(self) -> Text:
        return "action_guardar_ultima_pregunta"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        texto = tracker.latest_message.get("text", "")
        return [SlotSet("ultima_pregunta", texto)]


class ActionConsultarLLMMedico(Action):
    """
    Conecta directamente con Ollama para usar LLaMA 3.
    Incluye RAG: busca casos clínicos relevantes en la BD antes de generar respuesta.
    """

    def name(self) -> Text:
        return "action_consultar_llm_medico"

    def _buscar_casos_relevantes(self, pregunta: str) -> str:
        """
        Busca casos clínicos relevantes en la base de datos.
        Retorna un string con información de los casos encontrados.
        """
        try:
            # Extraer palabras clave de la pregunta
            palabras_clave = ["tuberculosis", "TB", "síntomas", "diagnóstico", "tratamiento"]
            query = ""
            for palabra in palabras_clave:
                if palabra.lower() in pregunta.lower():
                    query = palabra
                    break
            
            if not query:
                # Usar la pregunta completa como query
                query = pregunta
            
            # Consultar el backend
            resp = requests.get(
                f"{BACKEND_URL}/api/cases/search",
                params={"q": query, "limit": 3},
                timeout=5
            )
            
            if resp.status_code == 200:
                cases = resp.json()
                if cases:
                    contexto = "\n\n=== CASOS CLÍNICOS RELEVANTES DE LA BASE DE DATOS ===\n"
                    for i, case in enumerate(cases, 1):
                        contexto += f"\nCaso {i}: {case.get('title', 'Sin título')}\n"
                        contexto += f"Descripción: {case.get('description', 'N/A')}\n"
                    contexto += "\n=== FIN DE CASOS CLÍNICOS ===\n"
                    return contexto
        except Exception as e:
            print(f"[INFO] No se pudieron obtener casos clínicos: {e}")
        
        return ""

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
        ) -> List[Dict[Text, Any]]:

        pregunta = tracker.get_slot("ultima_pregunta") or tracker.latest_message.get("text", "")
        intent = tracker.latest_message.get("intent", {}).get("name", "desconocido")

        # Buscar casos clínicos relevantes
        casos_contexto = self._buscar_casos_relevantes(pregunta)

        system_prompt = (
            "Eres un médico especialista en medicina interna con amplia experiencia clínica y académica. "
            "Tu función es proporcionar información médica educativa de alta calidad, basada en evidencia científica actual. "
            "\n\nCARACTERÍSTICAS DE TUS RESPUESTAS:\n"
            "- Usa terminología médica precisa y apropiada\n"
            "- Explica fisiopatología, diagnóstico diferencial y manejo clínico de manera estructurada\n"
            "- Cita guías clínicas y evidencia cuando sea relevante\n"
            "- Mantén un tono profesional, objetivo y educativo\n"
            "- Organiza la información de forma sistemática (definición, etiología, clínica, diagnóstico, tratamiento)\n"
            "\n\nIMPORTANTE - DISCLAIMER OBLIGATORIO:\n"
            "- Esta información es con fines EXCLUSIVAMENTE EDUCATIVOS\n"
            "- NO sustituye la evaluación clínica presencial\n"
            "- NO proporciona diagnósticos ni tratamientos para casos reales\n"
            "- Ante cualquier situación clínica real, se debe consultar con un profesional de la salud\n"
            "\n\nÁREAS DE EXPERTISE: Medicina interna, enfermedades infecciosas, neumología, cardiología, "
            "gastroenterología, endocrinología, nefrología, y medicina de urgencias."
        )

        # Si hay casos relevantes, agregarlos al contexto
        if casos_contexto:
            system_prompt += (
                "\n\nDISPONES DE LOS SIGUIENTES CASOS CLÍNICOS EDUCATIVOS ALMACENADOS: "
                + casos_contexto +
                "\n\nPuedes usar la información de estos casos para enriquecer tu respuesta, "
                "mencionando ejemplos reales de pacientes (sin identificar datos personales). "
                "Si los casos son relevantes para la pregunta, úsalos como referencia."
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pregunta}
        ]

        try:
            # Llamada directa a Ollama
            resp = requests.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": LLM_MODEL,
                    "messages": messages,
                    "stream": False
                },
                timeout=120
            )
            resp.raise_for_status()
            data = resp.json()
            respuesta_modelo = data.get("message", {}).get("content", "")
            
            if not respuesta_modelo:
                respuesta_modelo = (
                    "No pude generar una respuesta en este momento. "
                    "Intenta reformular tu pregunta o consulta con un profesional de la salud."
                )
        except Exception as e:
            print(f"[ERROR] Error al conectar con Ollama: {e}")
            respuesta_modelo = (
                "En este momento no puedo acceder al modelo educativo de IA. "
                "Intenta nuevamente más tarde. Recuerda que siempre debes consultar "
                "a un profesional de la salud ante cualquier duda clínica real."
            )

        dispatcher.utter_message(text=respuesta_modelo)
        return []


class ActionAnalizarImagenTB(Action):
    """
    Llama a un microservicio de análisis de imágenes (modelo TB).
    La forma concreta de pasar la imagen (archivo, URL, id) la defines tú
    en el frontend/backend, usando por ejemplo el slot 'imagen_id'.
    """

    def name(self) -> Text:
        return "action_analizar_imagen_tb"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
        ) -> List[Dict[Text, Any]]:

        imagen_id = tracker.get_slot("imagen_id")

        if not imagen_id:
            dispatcher.utter_message(
                text=(
                    "Para este análisis educativo necesito que se envíe correctamente la imagen "
                    "desde la interfaz. Intenta subirla nuevamente."
                )
            )
            return []

        payload = {
            "image_id": imagen_id,
            "mode": "educational_only",
        }

        try:
            resp = requests.post(TB_IMAGE_API_URL, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            prob_tb = data.get("prob_tb", None)
            findings = data.get("findings", [])
            explanation = data.get("educational_explanation", "")

            mensaje = "Análisis educativo de la imagen:\n\n"

            if prob_tb is not None:
                mensaje += f"- Estimación educativa de compatibilidad con tuberculosis: {prob_tb:.2f}\n"

            if findings:
                mensaje += "- Hallazgos radiológicos reportados (a nivel docente): " + ", ".join(findings) + "\n"

            if explanation:
                mensaje += "\n" + explanation + "\n"

            mensaje += (
                "\nRecuerda que este análisis es solo para fines formativos y no debe utilizarse "
                "para diagnóstico clínico real. Para cualquier decisión sobre pacientes, "
                "se debe recurrir a un profesional de la salud."
            )

            dispatcher.utter_message(text=mensaje)

        except Exception:
            dispatcher.utter_message(
                text=(
                    "En este momento no puedo acceder al servicio educativo de análisis de imágenes. "
                    "Intenta nuevamente más tarde. Este asistente no reemplaza la evaluación radiológica "
                    "de un profesional."
                )
            )

        return []
