from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()

client = OpenAI(
    organization=os.getenv("openorg"),
    project=os.getenv("openproj"),
    api_key=os.getenv("openapi")
)

def create_openai_chat_completion(model, messages, temperature=0.5, max_tokens=100, stop=None):
    """
    :model: The model to use for the chat completion.
    :messages: A list of messages for the chat completion.
    :temperature: Controls randomness. Lower is less random.
    :max_tokens: The maximum number of tokens to generate.
    :stop: Sequence where the API will stop generating further tokens.
    :return: The API response as a dictionary.
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop
        )
        return response
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


if __name__ == "__main__":
    model = "gpt-3.5-turbo"
    pantry = ['banana', 'apple', 'bread', 'milk']
    msgs = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": f"Recommend a recipe using {', '.join(pantry)}."}]
    response = create_openai_chat_completion(model=model, messages=msgs)
    print(response)