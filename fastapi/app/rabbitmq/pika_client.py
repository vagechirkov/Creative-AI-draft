import json
import uuid

import pika as pika
from aio_pika import connect_robust
from envparse import env


class PikaClient:
    def __init__(self, process_callable):
        self.publish_queue_name = env(
            'PUBLISH_TASK_QUEUE', 'noname_publish_task_queue')
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=env('RABBIT_HOST', '127.0.0.1'))
        )
        self.channel = self.connection.channel()
        self.publish_queue = self.channel.queue_declare(
            queue=self.publish_queue_name)
        self.callback_queue = self.publish_queue.method.queue
        self.response = None
        self.process_callable = process_callable

    async def consume(self, loop):
        """Setup message listener with the current running loop"""
        connection = await connect_robust(
            host=env('RABBIT_HOST', '127.0.0.1'), port=5672, loop=loop)
        channel = await connection.channel()
        queue = await channel.declare_queue(
            env('CONSUME_RESULT_QUEUE', 'noname_consume_result_queue'))
        await queue.consume(self.process_incoming_message, no_ack=False)
        return connection

    async def process_incoming_message(self, message):
        """Processing incoming message from RabbitMQ"""
        await message.ack()
        body = message.body
        if body:
            self.process_callable(json.loads(body))

    def send_message(self, message: dict):
        """Method to publish message to RabbitMQ"""
        self.channel.basic_publish(
            exchange='',
            routing_key=self.publish_queue_name,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=str(uuid.uuid4())
            ),
            body=json.dumps(message)
        )
