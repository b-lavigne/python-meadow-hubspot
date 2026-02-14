FROM public.ecr.aws/lambda/python:3.12

# Copy requirements and wheels
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
COPY wheels/*.whl ${LAMBDA_TASK_ROOT}/wheels/

# Install with flags to ensure fresh library installation
RUN pip install --no-cache-dir --force-reinstall ${LAMBDA_TASK_ROOT}/wheels/*.whl && \
    pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt && \
    rm -rf ${LAMBDA_TASK_ROOT}/wheels

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD [ "lambda_function.lambda_handler" ]