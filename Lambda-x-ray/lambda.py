import aws_xray_sdk.core
import boto3
import requests
import os
import base64
import io
import mimetypes
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
aws_xray_sdk.core.patch_all()


def lambda_handler(event, context):
    try:
        session = boto3.Session()
        s3 = session.resource('s3')

        bucket_name = os.getenv('BUCKET_NAME')

        if not bucket_name:
            logger.error(
                "La variable de entorno BUCKET_NAME no está configurada.")
            return {
                'statusCode': 500,
                'body': 'Error de configuración: BUCKET_NAME no encontrado.'
            }
        with aws_xray_sdk.core.xray_recorder.capture('call_dog_api'):
            endpoint = 'https://dog.ceo/api/breeds/image/random'

            api_response = requests.get(endpoint)

            api_response.raise_for_status()

            api_data = api_response.json()
            image_url = api_data.get('message')

            if not image_url:
                raise ValueError(
                    "La API de perros no devolvió una URL de imagen válida.")

            # Obtener el nombre del archivo
            image_name = image_url.split('/')[-1]

            # Descargar la imagen
            image_content = requests.get(image_url, stream=True).content

            logger.info(f"Imagen descargada con éxito: {image_name}")

        with aws_xray_sdk.core.xray_recorder.capture('save_dog_to_s3'):
            # Determinar el ContentType basado en la extensión
            file_extension = '.' + image_name.split('.')[-1]
            contenttype = mimetypes.types_map.get(file_extension, 'image/jpeg')

            bucket = s3.Bucket(bucket_name)

            # Usar io.BytesIO para manejar el contenido de la imagen en memoria
            bucket.upload_fileobj(
                io.BytesIO(image_content),
                image_name,
                ExtraArgs={'ContentType': contenttype}
            )
            logger.info(f"Imagen {image_name} subida a S3/{bucket_name}")

        # 4. Generar la Respuesta (Simulando una respuesta de API Gateway)
        # Se codifica la imagen descargada para enviarla en el cuerpo de la respuesta.
        response_body_base64 = base64.b64encode(image_content).decode('utf-8')

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': contenttype,
                # Permite a cualquier origen acceder (CORS)
                'Access-Control-Allow-Origin': '*'
            },
            'body': response_body_base64,
            'isBase64Encoded': True
        }
    except requests.HTTPError as e:
        logger.error(f"Error al llamar a la API externa: {e}")
        return {
            'statusCode': e.response.status_code,
            'body': f"Error en la API externa: {e.response.text}"
        }
    except Exception as e:
        logger.error(f"Error desconocido en la función: {e}")
        return {
            'statusCode': 500,
            'body': f"Error interno del servidor: {str(e)}"
        }
