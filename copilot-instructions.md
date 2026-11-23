# Context for Copilot

## Who we are
We're a pair of design students in HCDE 310, learning Python and Flask.

## How we work with AI (Stage 4: spec first)
- Don't write specs or checks for us. Before writing code, ask us for what it should do, its inputs and outputs, and 2 or 3 checks, then wait for our answer. After we write them, you may point out what's missing.
- Build in small pieces. Before you change files, tell us which ones. Don't commit.

## How we like to work
Give us the code all at once, but explain each part of the code in a way that isn't super technical. Someone should be able to explain what the function/code does without having a ton of coding knowledge.

## Our project
This product is for someone who lives in the USA and wants to find a meal that fits the type or mood of the weather they are experiencing, whether it be extremely cold, hot, rainy, or sunny. Our APIs are Zippopotam.us, Open-Meteo, and RecipesAPI. We are also using Claude as our LLM to map weather to mood.  
Claude requires a key, as does RecipeAPI. A limit for Open-Meteo is that it cannot exceed 10000 calls per day for its rate limit.

## Not decided yet
Not exactly sure of the full functionality of the project, whether users can favorite or save recipes, or how exactly the LLM is going to map mood to weather and then source recipes from that 

## Wrap up
When we say "wrap up": add an entry to ai_use.md with the date and the files and functions you wrote or changed, one line each, starting with "AI draft: check me." Leave "Reflection:" blank. Suggest a commit message. Don't commit until we say yes.
