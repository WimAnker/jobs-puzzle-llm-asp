from openai import OpenAI

client = OpenAI(api_key="***REMOVED***")


models = client.models.list()

for m in models.data:
    print(m.id)
