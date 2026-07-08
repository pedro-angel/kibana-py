WorkflowsClient
===============

Client for the Kibana Workflows API.

Workflows automate sequences of steps (connector calls, Elasticsearch
requests, Kibana actions, ...) defined in a YAML document. The Workflows APIs
are generally available since Kibana 9.4.0.

Workflows are space-scoped resources: a workflow created in one space is not
visible from another space. Every method accepts an optional ``space_id`` to
target a specific space.

.. currentmodule:: kibana._sync.client.workflows

.. autoclass:: WorkflowsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Creating and Running Workflows

   Workflows are defined in YAML:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      yaml_definition = """
      name: my-workflow
      enabled: true
      triggers:
        - type: manual
      steps:
        - name: log_step
          type: console
          with:
            message: "hello world"
      """

      # Create the workflow
      created = client.workflows.create(yaml=yaml_definition)
      workflow_id = created.body["id"]

      # Run it manually
      run = client.workflows.run(id=workflow_id, inputs={})
      execution_id = run.body["workflowExecutionId"]

   .. rubric:: Inspecting Executions

   .. code-block:: python

      # Get a single execution
      execution = client.workflows.get_execution(execution_id=execution_id)
      print(execution.body["status"])

      # List executions of a workflow
      executions = client.workflows.get_executions(workflow_id=workflow_id)

      # Step-level details and logs
      steps = client.workflows.get_step_executions(workflow_id=workflow_id)
      logs = client.workflows.get_execution_logs(execution_id=execution_id)

   .. rubric:: Searching and Managing Workflows

   .. code-block:: python

      # Search workflows
      found = client.workflows.get_all(query="my-workflow", size=10)
      for workflow in found.body["results"]:
          print(workflow["id"], workflow["name"])

      # Update the YAML definition
      client.workflows.update(id=workflow_id, yaml=yaml_definition)

      # Clone a workflow
      clone = client.workflows.clone(id=workflow_id)

      # Delete workflows
      client.workflows.delete(id=workflow_id)

   .. rubric:: Testing Workflows

   Test a workflow definition without persisting it:

   .. code-block:: python

      test_run = client.workflows.test(
          workflow_yaml=yaml_definition, inputs={}
      )

AsyncWorkflowsClient
--------------------

Asynchronous version of the WorkflowsClient for use with async/await syntax.

.. autoclass:: kibana._async.client.workflows.AsyncWorkflowsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncWorkflowsClient provides the same methods as WorkflowsClient but
   all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create and run a workflow (async)
              created = await client.workflows.create(
                  yaml="""
                  name: async-workflow
                  enabled: true
                  triggers:
                    - type: manual
                  steps:
                    - name: log_step
                      type: console
                      with:
                        message: "hello from async"
                  """
              )
              run = await client.workflows.run(
                  id=created.body["id"], inputs={}
              )

              # Poll the execution (async)
              execution = await client.workflows.get_execution(
                  execution_id=run.body["workflowExecutionId"]
              )

              # Delete (async)
              await client.workflows.delete(id=created.body["id"])

      asyncio.run(main())
