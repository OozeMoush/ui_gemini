Text generation

bookmark_border

This page shows you how to send chat prompts to a Gemini model by using the Google Cloud console, REST API, and supported SDKs.

To learn how to add images and other media to your request, see Image understanding.

For a list of languages supported by Gemini, see Language support.

To explore the generative AI models and APIs that are available on Vertex AI, go to Model Garden in the Google Cloud console.

Go to Model Garden

If you're looking for a way to use Gemini directly from your mobile and web apps, see the Firebase AI Logic client SDKs for Swift, Android, Web, Flutter, and Unity apps.

Generate text
For testing and iterating on chat prompts, we recommend using the Google Cloud console. To send prompts programmatically to the model, you can use the REST API, Google Gen AI SDK, Vertex AI SDK for Python, or one of the other supported libraries and SDKs.

You can use system instructions to steer the behavior of the model based on a specific need or use case. For example, you can define a persona or role for a chatbot that responds to customer service requests. For more information, see the system instructions code samples.

You can use the Google Gen AI SDK to send requests if you're using Gemini 2.0 Flash.

Here is a simple text generation example.

```bash
pip install --upgrade google-genai
To learn more, see the SDK reference documentation.
```

Set environment variables to use the Gen AI SDK with Vertex AI:


```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```python
from google import genai
from google.genai.types import HttpOptions

client = genai.Client(http_options=HttpOptions(api_version="v1"))
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="How does AI work?",
)
print(response.text)
# Example response:
# Okay, let's break down how AI works. It's a broad field, so I'll focus on the ...
#
# Here's a simplified overview:
# ...
```

Streaming and non-streaming responses
You can choose whether the model generates streaming responses or non-streaming responses. For streaming responses, you receive each response as soon as its output token is generated. For non-streaming responses, you receive all responses after all of the output tokens are generated.

Here is a streaming text generation example.

Python
Before trying this sample, follow the Python setup instructions in the Vertex AI quickstart using client libraries. For more information, see the Vertex AI Python API reference documentation.

To authenticate to Vertex AI, set up Application Default Credentials. For more information, see Set up authentication for a local development environment.



```python
from google import genai
from google.genai.types import HttpOptions

client = genai.Client(http_options=HttpOptions(api_version="v1"))
chat_session = client.chats.create(model="gemini-2.5-flash")

for chunk in chat_session.send_message_stream("Why is the sky blue?"):
    print(chunk.text, end="")
# Example response:
# The
#  sky appears blue due to a phenomenon called **Rayleigh scattering**. Here's
#  a breakdown of why:
# ...
```


Content generation parameters

This page shows the optional sampling parameters you can set in a request to a model. The parameters available for each model may differ. For more information, see the reference documentation.

Token sampling parameters
Top-P
Top-P changes how the model selects tokens for output. Tokens are selected from the most probable to least probable until the sum of their probabilities equals the top-P value. For example, if tokens A, B, and C have a probability of 0.3, 0.2, and 0.1 and the top-P value is 0.5, then the model will select either A or B as the next token by using temperature and excludes C as a candidate.

Specify a lower value for less random responses and a higher value for more random responses.

For more information, see topP.
Temperature
The temperature is used for sampling during response generation, which occurs when topP and topK are applied. Temperature controls the degree of randomness in token selection. Lower temperatures are good for prompts that require a less open-ended or creative response, while higher temperatures can lead to more diverse or creative results. A temperature of 0 means that the highest probability tokens are always selected. In this case, responses for a given prompt are mostly deterministic, but a small amount of variation is still possible.

If the model returns a response that's too generic, too short, or the model gives a fallback response, try increasing the temperature.

Lower temperatures lead to predictable (but not completely deterministic) results. For more information, see temperature.

Stopping parameters
Maximum output tokens
Set maxOutputTokens to limit the number of tokens generated in the response. A token is approximately four characters, so 100 tokens correspond to roughly 60-80 words. Set a low value to limit the length of the response.

Stop sequences
Define strings in stopSequences to tell the model to stop generating text if one of the strings is encountered in the response. If a string appears multiple times in the response, then the response is truncated where the string is first encountered. The strings are case-sensitive.

Token penalization parameters
Frequency penalty
Positive values penalize tokens that repeatedly appear in the generated text, decreasing the probability of repeating content. The minimum value is -2.0. The maximum value is up to, but not including, 2.0. For more information, see frequencyPenalty.

Presence penalty
Positive values penalize tokens that already appear in the generated text, increasing the probability of generating more diverse content. The minimum value is -2.0. The maximum value is up to, but not including, 2.0. For more information, see presencePenalty.

Advanced parameters
Use these parameters to return more information about the tokens in the response or to control the variability of the response.

Preview

This product or feature is subject to the "Pre-GA Offerings Terms" in the General Service Terms section of the Service Specific Terms. Pre-GA products and features are available "as is" and might have limited support. For more information, see the launch stage descriptions.

Log probabilities of output tokens
Returns the log probabilities of the top candidate tokens at each generation step. The model's chosen token might not be the same as the top candidate token at each step. Specify the number of candidates to return by using an integer value in the range of 1-20. For more information, see logprobs. You also need to set the responseLogprobs parameter to true to use this feature.

The responseLogprobs parameter returns the log probabilities of the tokens that were chosen by the model at each step.

For more information, see the Intro to Logprobs notebook.

Seed
When seed is fixed to a specific value, the model makes a best effort to provide the same response for repeated requests. Deterministic output isn't guaranteed. Also, changing the model or parameter settings, such as the temperature, can cause variations in the response even when you use the same seed value. By default, a random seed value is used. For more information, see seed.

Example
Here is an example that uses parameters to tune a model's response.


```bash
pip install --upgrade google-genai
```
To learn more, see the SDK reference documentation.

Set environment variables to use the Gen AI SDK with Vertex AI:


```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```python
from google import genai
from google.genai.types import GenerateContentConfig, HttpOptions

client = genai.Client(http_options=HttpOptions(api_version="v1"))
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Why is the sky blue?",
    # See the SDK documentation at
    # https://googleapis.github.io/python-genai/genai.html#genai.types.GenerateContentConfig
    config=GenerateContentConfig(
        temperature=0,
        candidate_count=1,
        response_mime_type="application/json",
        top_p=0.95,
        top_k=20,
        seed=5,
        max_output_tokens=500,
        stop_sequences=["STOP!"],
        presence_penalty=0.0,
        frequency_penalty=0.0,
    ),
)
print(response.text)
# Example response:
# {
#   "explanation": "The sky appears blue due to a phenomenon called Rayleigh scattering. When ...
# }

```