import os
import json
import boto3

def invoke_lambda(function_name, payload, invocation_type="RequestResponse"):
    """
    Invoke another Lambda function using AWS SDK.
    
    Args:
        function_name: Target Lambda function name (can be from environment variable)
        payload: Dict/object to send as payload
        invocation_type: "RequestResponse" (sync) or "Event" (async)
    
    Returns:
        Parsed response payload for RequestResponse, None for Event
    """
    lambda_client = boto3.client('lambda')
    
    # If function_name is an environment variable reference, resolve it
    if function_name.startswith('${') and function_name.endswith('}'):
        env_var_name = function_name[2:-1]
        function_name = os.environ.get(env_var_name)
        if not function_name:
            raise ValueError(f"Environment variable {env_var_name} not found")
    
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType=invocation_type,
            Payload=json.dumps(payload)
        )
        
        if invocation_type == "RequestResponse":
            # Parse the response payload
            response_payload = json.loads(response['Payload'].read().decode('utf-8'))
            return response_payload
        else:
            # Event invocation returns None
            return None
            
    except Exception as e:
        raise Exception(f"Failed to invoke Lambda {function_name}: {str(e)}")
