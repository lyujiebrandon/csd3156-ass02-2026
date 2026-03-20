import json
import os
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")

CONNECTIONS_TABLE = os.environ["CONNECTIONS_TABLE"]
AWS_REGION_NAME = os.environ["AWS_REGION_NAME"]

connections_table = dynamodb.Table(CONNECTIONS_TABLE)

# WebSocket connection TTL: 2 hours
CONNECTION_TTL_SECONDS = 7200


def lambda_handler(event, context):
    route_key = event["requestContext"]["routeKey"]
    connection_id = event["requestContext"]["connectionId"]

    if route_key == "$connect":
        return handle_connect(event, connection_id)
    elif route_key == "$disconnect":
        return handle_disconnect(connection_id)
    else:
        return handle_message(event, connection_id)


def handle_connect(event, connection_id):
    """Store new WebSocket connection. Extract user_id from Cognito authorizer."""
    # Cognito user_id is passed as a query param during WS handshake
    query_params = event.get("queryStringParameters") or {}
    user_id = query_params.get("user_id", "anonymous")

    now = int(datetime.now(timezone.utc).timestamp())
    expires_at = now + CONNECTION_TTL_SECONDS

    connections_table.put_item(Item={
        "connection_id": connection_id,
        "user_id": user_id,
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at,
    })

    return {"statusCode": 200, "body": "Connected"}


def handle_disconnect(connection_id):
    """Remove WebSocket connection record."""
    connections_table.delete_item(Key={"connection_id": connection_id})
    return {"statusCode": 200, "body": "Disconnected"}


def handle_message(event, connection_id):
    """Handle incoming WebSocket messages (e.g. ping/pong)."""
    body = json.loads(event.get("body") or "{}")
    action = body.get("action")

    if action == "ping":
        _send_message(event, connection_id, {"type": "pong"})

    return {"statusCode": 200, "body": "OK"}


def _send_message(event, connection_id, payload):
    """Push a message back to a specific WebSocket connection."""
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]
    endpoint = f"https://{domain}/{stage}"

    apigw = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=endpoint,
        region_name=AWS_REGION_NAME,
    )

    try:
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload).encode("utf-8"),
        )
    except apigw.exceptions.GoneException:
        connections_table.delete_item(Key={"connection_id": connection_id})
