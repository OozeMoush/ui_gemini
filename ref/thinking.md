Thinking 

bookmark_border
Release Notes


Preview

This feature is subject to the "Pre-GA Offerings Terms" in the General Service Terms section of the Service Specific Terms. Pre-GA features are available "as is" and might have limited support. For more information, see the launch stage descriptions.

To see an example of Gemini 2.5 Flash, run the "Intro to Gemini 2.5 Flash" Jupyter notebook in one of the following environments:

Open in Colab | Open in Colab Enterprise | Open in Vertex AI Workbench user-managed notebooks | View on GitHub

Thinking models are trained to generate the "thinking process" the model goes through as part of its response. As a result, thinking models are capable of stronger reasoning capabilities in its responses than equivalent base models.

The thinking process is enabled by default. When you use Vertex AI Studio, you can view the full thinking process together with the model's generated response.

Supported models
Thinking is supported in the following models:

Gemini 2.5 Pro preview
Gemini 2.5 Flash preview
Use a thinking model
The thinking process is enabled by default for both Gemini 2.5 Flash and Gemini 2.5 Pro. To use thinking, do the following:

Console
Gen AI SDK for Python
Install


pip install --upgrade google-genai
To learn more, see the SDK reference documentation.

Set environment variables to use the Gen AI SDK with Vertex AI:



# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True


```python
from google import genai

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-pro-preview-05-06",
    contents="solve x^2 + 4x + 4 = 0",
)
print(response.text)
# Example Response:
#     Okay, let's solve the quadratic equation x² + 4x + 4 = 0.
#
#     We can solve this equation by factoring, using the quadratic formula, or by recognizing it as a perfect square trinomial.
#
#     **Method 1: Factoring**
#
#     1.  We need two numbers that multiply to the constant term (4) and add up to the coefficient of the x term (4).
#     2.  The numbers 2 and 2 satisfy these conditions: 2 * 2 = 4 and 2 + 2 = 4.
#     3.  So, we can factor the quadratic as:
#         (x + 2)(x + 2) = 0
#         or
#         (x + 2)² = 0
#     4.  For the product to be zero, the factor must be zero:
#         x + 2 = 0
#     5.  Solve for x:
#         x = -2
#
#     **Method 2: Quadratic Formula**
#
#     The quadratic formula for an equation ax² + bx + c = 0 is:
#     x = [-b ± sqrt(b² - 4ac)] / (2a)
#
#     1.  In our equation x² + 4x + 4 = 0, we have a=1, b=4, and c=4.
#     2.  Substitute these values into the formula:
#         x = [-4 ± sqrt(4² - 4 * 1 * 4)] / (2 * 1)
#         x = [-4 ± sqrt(16 - 16)] / 2
#         x = [-4 ± sqrt(0)] / 2
#         x = [-4 ± 0] / 2
#         x = -4 / 2
#         x = -2
#
#     **Method 3: Perfect Square Trinomial**
#
#     1.  Notice that the expression x² + 4x + 4 fits the pattern of a perfect square trinomial: a² + 2ab + b², where a=x and b=2.
#     2.  We can rewrite the equation as:
#         (x + 2)² = 0
#     3.  Take the square root of both sides:
#         x + 2 = 0
#     4.  Solve for x:
#         x = -2
#
#     All methods lead to the same solution.
#
#     **Answer:**
#     The solution to the equation x² + 4x + 4 = 0 is x = -2. This is a repeated root (or a root with multiplicity 2).
```

View thought summaries
Experimental

This feature is subject to the "Pre-GA Offerings Terms" in the General Service Terms section of the Service Specific Terms. Pre-GA features are available "as is" and might have limited support. For more information, see the launch stage descriptions.

Thought summaries are the abbreviated output of the thinking process that the model went through when generating its response. You can view thought summaries in both Gemini 2.5 Flash and Gemini 2.5 Pro. To view thought summaries, do the following:

Console
Gen AI SDK for Python
Install


pip install --upgrade google-genai
To learn more, see the SDK reference documentation.

Set environment variables to use the Gen AI SDK with Vertex AI:



# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True


```python
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-pro-preview-05-06",
    contents="solve x^2 + 4x + 4 = 0",
    config=GenerateContentConfig(
        thinking_config=ThinkingConfig(include_thoughts=True)
    ),
)

print(response.text)
# Example Response:
#     Okay, let's solve the quadratic equation x² + 4x + 4 = 0.
#     ...
#     **Answer:**
#     The solution to the equation x² + 4x + 4 = 0 is x = -2. This is a repeated root (or a root with multiplicity 2).

for part in response.candidates[0].content.parts:
    if part and part.thought:  # show thoughts
        print(part.text)
# Example Response:
#     **My Thought Process for Solving the Quadratic Equation**
#
#     Alright, let's break down this quadratic, x² + 4x + 4 = 0. First things first:
#     it's a quadratic; the x² term gives it away, and we know the general form is
#     ax² + bx + c = 0.
#
#     So, let's identify the coefficients: a = 1, b = 4, and c = 4. Now, what's the
#     most efficient path to the solution? My gut tells me to try factoring; it's
#     often the fastest route if it works. If that fails, I'll default to the quadratic
#     formula, which is foolproof. Completing the square? It's good for deriving the
#     formula or when factoring is difficult, but not usually my first choice for
#     direct solving, but it can't hurt to keep it as an option.
#
#     Factoring, then. I need to find two numbers that multiply to 'c' (4) and add
#     up to 'b' (4). Let's see... 1 and 4 don't work (add up to 5). 2 and 2? Bingo!
#     They multiply to 4 and add up to 4. This means I can rewrite the equation as
#     (x + 2)(x + 2) = 0, or more concisely, (x + 2)² = 0. Solving for x is now
#     trivial: x + 2 = 0, thus x = -2.
#
#     Okay, just to be absolutely certain, I'll run the quadratic formula just to
#     double-check. x = [-b ± √(b² - 4ac)] / 2a. Plugging in the values, x = [-4 ±
#     √(4² - 4 * 1 * 4)] / (2 * 1). That simplifies to x = [-4 ± √0] / 2. So, x =
#     -2 again – a repeated root. Nice.
#
#     Now, let's check via completing the square. Starting from the same equation,
#     (x² + 4x) = -4. Take half of the b-value (4/2 = 2), square it (2² = 4), and
#     add it to both sides, so x² + 4x + 4 = -4 + 4. Which simplifies into (x + 2)²
#     = 0. The square root on both sides gives us x + 2 = 0, therefore x = -2, as
#      expected.
#
#     Always, *always* confirm! Let's substitute x = -2 back into the original
#     equation: (-2)² + 4(-2) + 4 = 0. That's 4 - 8 + 4 = 0. It checks out.
#
#     Conclusion: the solution is x = -2. Confirmed.

```

Control the thinking budget
For Gemini 2.5 Flash only, you can control how much the model thinks during its responses. This upper limit is called the thinking budget and applies to the model's full thought process. By default, the model automatically controls how much it thinks up to a maximum of 8,192 tokens. This default applies to both Gemini 2.5 Flash and Gemini 2.5 Pro.

Gemini 2.5 Flash lets you manually set the upper limit on the number of tokens in situations where you might need more or less tokens than the default thinking budget. You can set a lower token limit for less complex tasks, or a higher limit for more complex ones.

The maximum thinking budget that you can set is 24,576 tokens, and the minimum you can set and still have thinking turned on is 1. However, the floor for the thinking budget is 1,024 tokens, meaning any value that you set under 1,024 tokens is reset to 1,024 in the API.

If you set the thinking budget to 0, thinking is turned off.

Console
Gen AI SDK for Python
Open Vertex AI Studio > Create prompt.
In the Model panel, click Switch model and select one of the supported models from the menu.
For the Thinking budget (Gemini 2.5 Flash only), set it to Manual and then use the slider to adjust the thinking budget limit.
Prompting techniques
Effective prompting is crucial for maximizing the benefits of the Gemini thinking models. This section outlines some prompting practices for thinking models.

Begin with general instructions that describe the desired outcome. Start with a simple prompt and observe the model's initial thoughts on how to respond.

Prompt:

Describe the most unusual or striking architectural feature you've ever seen in a building or structure.
Response:

<...>
The most unusual architectural feature that has truly stayed with me is the "floating roof" of the
Heydar Aliyev Center in Baku, Azerbaijan, designed by Zaha Hadid Architects.

Visually, it's breathtaking. Imagine a vast, undulating landscape of pure white, seemingly draped
over the building. It's not just a roof in the traditional sense; it's an extension of the ground,
flowing seamlessly upwards and over the building's various spaces before curving back down to meet
the earth again. There are no sharp angles, no rigid lines. Instead, everything is fluid, organic,
and continuous. It resembles a giant, pristine white wave frozen in motion, or perhaps a sand dune
sculpted by an unseen wind.
<...>
(gemini-2.5-pro-exp-03-25)
Provide step-by-step instructions
If the initial attempt does not yield the desired result, refine your prompt by providing more explicit step-by-step instructions to guide Gemini through the problem-solving process for a more focused approach. This allows you steer the model's initial understanding of the task with explicit suggestions and guidance.

Prompt:

Now imagine that architectural feature is not just for looks, but has a specific function or
purpose related to the building's environment or the people who use it. Explain what that
function could be and how it enhances the building's overall design and usability.
Response:

<...>
Let's imagine that the "floating roof" of the Heydar Aliyev Center is not purely aesthetic but
serves a crucial environmental and user-centric function: it's designed as a sophisticated climate
moderator and natural ventilation system for the Baku environment.

Here's how this function would work and enhance the building:

Function: Passive Climate Control and Natural Ventilation System

Shading and Solar Heat Mitigation: The undulating curves of the white GFRC roof are strategically
shaped and oriented to provide optimal shading throughout the day, year-round. Baku experiences
intense sun, especially during the summer. The overhanging curves, acting like giant brise-soleils,
would block direct sunlight from hitting the building's glass facade, significantly reducing solar
heat gain. The varying heights and depths of the curves would create dynamic shade patterns, ensuring
that different parts of the building are shaded at different times of the day, optimizing comfort
and reducing the need for excessive air conditioning. The white color of the GFRC further enhances
this by reflecting a large portion of the solar radiation.
<...>
(gemini-2.5-pro-exp-03-25)
Multishot prompting with thinking
Multishot prompting in conjunction with thinking can further enhance Gemini's understanding and improve the accuracy of its responses. Provide several examples of input-output pairs, demonstrating the desired behavior and output format in your prompt.

Prompt:

Example 1:
User: What is the tallest mountain in the world?
Assistant: Mount Everest

Example 2:
User: What is the largest ocean?
Assistant: Pacific Ocean

User: What is the longest river in the world?
Assistant:
Response:

Amazon River
(gemini-2.5-pro-exp-03-25)
Defining output and behavior
When building an application where users will interact directly with the model, you may want to provide guidance for how Gemini's output and responses will sound and be formatted.

System instructions
System instructions are a set of instructions that the model processes before it processes prompts. They are recalled each time the model is prompted and tell the model how you want it to behave and respond. For example, you can include things like the role or persona, contextual information, and formatting instructions.

Prompt:

System Instruction: You are a helpful and concise coding tutor. Always provide code examples and explain them briefly.

User Prompt: Explain what is a closure in Javascript and give an example.
Response:

function outerFunction(outerVar) {
function innerFunction(innerVar) {
console.log(outerVar); // Accessing outerVar from outerFunction's scope
console.log(innerVar);
}
return innerFunction;
}

const closureExample = outerFunction('I am from outer');
closureExample('I am from inner');

Explanation:

A closure is created when a function (innerFunction in this example) is defined inside another function
(outerFunction) and the inner function remembers and has access to the variables from the outer
function's scope, even after the outer function has finished executing.

In the example:

outerFunction is called with 'I am from outer' and returns innerFunction.

closureExample now holds a reference to innerFunction.

When closureExample('I am from inner') is called, innerFunction executes.

Even though outerFunction has already finished, innerFunction can still access and use outerVar
(which is 'I am from outer') because of the closure.

In essence, the innerFunction "closes over" the variables of its outer function's scope, creating
a closure.
(gemini-2.5-pro-exp-03-25)
Verification and reflection
Include specific verification steps in either the system instructions or your prompts directly. For example, ask Gemini to verify its sources, review its reasoning, identify potential errors, and check its final answer.

Prompt:

Verify the following statement and provide your sources: The capital of Brazil is Rio de Janeiro.
Response:

The statement "The capital of Brazil is Rio de Janeiro" is incorrect.

The current capital of Brazil is Brasília.

Rio de Janeiro was the capital of Brazil for a significant period, from 1763 to 1960. However, the
capital was moved to Brasília in 1960 as part of a plan to develop the country's interior and create
a more centrally located capital.

Verification and Sources:

You can easily verify this information from numerous reliable sources:

Encyclopedias:

Britannica: Searching for "Brazil" on Britannica will clearly state Brasília as the capital.

https://www.britannica.com/place/Brazil (Look for the "Capital" information in the introductory summary or "Geography" section)

Wikipedia: The Wikipedia article for "Brazil" also states Brasília as the capital.

https://en.wikipedia.org/wiki/Brazil (Look in the infobox or introductory section)

Government and Official Sources:

CIA World Factbook: This is a highly reliable source for country information. Searching for "Brazil"
will list Brasília as the capital.

https://www.cia.gov/the-world-factbook/countries/brazil/ (Look under "Government" > "Capital")

Official Website of the Brazilian Government (if accessible and in English): While navigating official
government websites can sometimes be complex, they would definitively list Brasília as the capital.

Geographic Resources:

National Geographic: Their website and publications will confirm Brasília as the capital of Brazil.

Atlases and Geography Textbooks: Any modern atlas or geography textbook will list Brasília as the capital.

Why the confusion?

The confusion might arise because:

Rio de Janeiro is a very famous Brazilian city: It's a major tourist destination, known for its
beaches, Carnival, and iconic landmarks like Christ the Redeemer. Its past status as capital adds
to its historical significance and public recognition.

Historical context: Rio de Janeiro was the capital for a long time. People who learned about Brazil
in the past might remember it as the capital.

In conclusion, the statement is false. The capital of Brazil is Brasília, not Rio de Janeiro. Rio
de Janeiro was the former capital but is no longer the current capital.

You can confidently use the sources listed above to verify this information.
(gemini-2.5-pro-exp-03-25)
Debugging and steering
Vertex AI Studio provides developers access to the model's thoughts in the UI. This is helpful as a developer reviewing your prompt when debugging:

Analyze the thought process
Carefully review Gemini's thought process to identify any areas where it may have gone astray. This analysis can provide valuable clues for refining your prompts and getting your expected response consistently in your application.

Example Scenario: If Gemini's thought process shows it misunderstood a step in a complex instruction, you can refine the prompt to clarify that specific step.

Prompt:

Step 1: Summarize the following article about quantum physics.
Step 2: Translate the summary into Spanish.
Step 3: Extract the key entities from the Spanish summary.

Article: ... [Article Text] ...
Gemini's Thought Process Analysis (Example):

The user wants me to process an article about Google's new quantum chip called Willow in three steps:
Step 1: Summarize the article.
Step 2: Translate the summary into Spanish.
Step 3: Extract the key entities from the Spanish summary.

Let's break down each step.

Step 1: Summarize the article.
I need to read the article and identify the main points. The article is about Google's new quantum
chip, Willow, and its achievements. The key achievements are:

Exponential error reduction as qubits scale up.

Outperforming supercomputers in a benchmark computation (RCS).

Willow is a step towards commercially relevant quantum computing.

It's the first system below threshold for quantum error correction.

It achieved a benchmark computation in under 5 minutes that would take a supercomputer 10 septillion years.

It was fabricated in a new facility.

It has state-of-the-art performance and high quality qubits.

Google is looking towards real-world applications with Willow.

Quantum computing will benefit AI.

I will synthesize these points into a concise summary.

Step 2: Translate the summary into Spanish.
Once I have the summary in English, I will translate it into Spanish. I need to ensure the translation
is accurate and natural-sounding in Spanish.

Step 3: Extract the key entities from the Spanish summary.
After translating the summary, I will identify and extract the key entities. Key entities are typically
nouns or noun phrases that represent important objects, concepts, or actors. In this context, they
will likely include:

Names of chips (Willow, Sycamore)

Companies/Organizations (Google Quantum AI, Google Research)

Technologies (quantum chip, quantum computer, qubits, quantum error correction, superconducting
quantum system, classical computers, supercomputers, AI)

Benchmarks (random circuit sampling, RCS)

People (Julian Kelly, Peter Shor, David Deutsch, Sergio Boixo, Hartmut Neven, John Preskill)

Concepts (exponential error reduction, below threshold, beyond breakeven, state-of-the-art performance,
commercially relevant applications, quantum mechanics, multiverse, T1 times, system benchmarks,
algorithmic benchmarks)

I will need to carefully review the Spanish summary to identify these entities and list them out.

Provide corrective feedback
If you observe errors or inconsistencies in Gemini's reasoning, provide corrective feedback in your prompt and the system instructions to anticipate where the model's response may deviate from your desired outcome.

Prompt:

You are an expert in botany. When asked to identify a plant, focus on leaf shape, flower structure, and stem characteristics.

Identify this plant based on these characteristics: ... [Plant Characteristics Description] ...

Previous incorrect response focused on habitat only. Please disregard habitat and focus on morphology.
Refined Prompt (if needed based on thought process):

Previous incorrect response focused on habitat only. Please disregard habitat and focus on morphology.
Response:

Tabebuia vellosoi
(gemini-2.5-pro-exp-03-25)
Making the best of long outputs and long-form thinking
Thinking generates "thoughts" as part of the Token Output that showcases Gemini's detailed reasoning. To make the most of these outputs:

Review the reasoning
Pay close attention to Gemini's reasoning process (available in the Vertex AI Studio UI), how it broke down the task and the choices it made for your output. This can help you understand how it arrived at its conclusion.

Provide guidance in reasoning
If you want your output to be particularly lengthy, you may want to provide more guidance in your prompt to constrain the amount of thinking needed to accomplish the task presented in the prompt. This lets you reserve more of the token output for your response.

*Example: For a detailed report, you might specify sections and subsections in your prompt to guide Gemini's thinking and structure the output efficiently.

Prompt:

Generate a detailed report on the impact of climate change on coastal ecosystems.

Report Structure:

Introduction

Rising Sea Levels
2.1. Impact on Mangroves
2.2. Impact on Coral Reefs

Ocean Acidification
3.1. Impact on Shellfish
3.2. Impact on Plankton

Extreme Weather Events
4.1. Increased Storm Intensity
4.2. Coastal Erosion

Conclusion

Provide detailed analysis within each section.
Response:

<...>
Climate Change Impact on Coastal Ecosystems: A Detailed Report

1. Introduction

Coastal ecosystems, the dynamic interface between land and sea, are among the most productive and
biodiverse environments on Earth. They provide crucial ecosystem services, including coastal protection,
fisheries, carbon sequestration, and support for a vast array of species. However, these vital
ecosystems are increasingly threatened by the multifaceted impacts of climate change. Driven by
anthropogenic greenhouse gas emissions, climate change is manifesting in several interconnected ways
that are profoundly altering the physical and chemical conditions of coastal environments. This report
will delve into the key impacts of climate change on coastal ecosystems, focusing on rising sea levels,
ocean acidification, and extreme weather events, and their specific consequences for critical habitats
like mangroves and coral reefs, and key organisms like shellfish and plankton. Understanding these
impacts is crucial for developing effective conservation and management strategies to mitigate the
damage and enhance the resilience of these invaluable ecosystems.

2. Rising Sea Levels

Rising sea levels are a direct and significant consequence of global warming, driven by thermal
expansion of seawater and the melting of land ice (glaciers and ice sheets). This phenomenon poses a
direct threat to low-lying coastal ecosystems by inundating habitats, altering salinity regimes, and
increasing erosion rates. The rate of sea level rise is accelerating, and projections for the 21st
century indicate a continued upward trend, with potentially devastating consequences for coastal
environments.

2.1. Impact on Mangroves

Mangrove forests are unique coastal ecosystems found in tropical and subtropical intertidal zones.
They provide numerous benefits, including coastal protection against storms, nursery grounds for
fish and invertebrates, and significant carbon sequestration...
<...>
(gemini-2.5-pro-exp-03-25)