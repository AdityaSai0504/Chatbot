from flask import Flask, request, jsonify, send_from_directory
from chatterbot import ChatBot
import logging
import nltk
import re
import spacy
import wolframalpha
import requests

# Initialize logging
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.disabled = True

# Initialize spaCy model
nlp = spacy.load('en_core_web_sm')

# Set up logging to console and file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize External APIs
logger.debug('Initializing external APIs...')

# WolframAlpha clients
wolfram_math_client = wolframalpha.Client('8KLVPT-Q66AEW22U9')  # Replace with your math API key
wolfram_convo_client = wolframalpha.Client('8KLVPT-56K3VWLR8T')  # Replace with your conversational API key
wolfram_ShortAnswers_client = wolframalpha.Client('8KLVPT-WVRWKPRX6T')  # Replace with your ShortAnswers API key
wolfram_steps_client = wolframalpha.Client('8KLVPT-8EAQ4UPKH3')  # Replace with your Show steps API key
# Initialize OpenAI API
#openai.api_key = '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'  # Replace with your OpenAI API key

# Wit.ai token
WIT_AI_TOKEN = 'SDE4C7U6GI2NQ7LQKZYQFLUGB6DODMXJ'  # Replace with your Wit.ai server access token

# RapidAPI for recipes (Spoonacular)
# Spoonacular API
SPOONACULAR_API_KEY = 'e29abc4d4amshd5f7831e5c98832p190e62jsn3d1bd923feee'
SPOONACULAR_SEARCH_URL = "https://spoonacular-recipe-food-nutrition-v1.p.rapidapi.com/recipes/complexSearch"
SPOONACULAR_RECIPE_URL = "https://spoonacular-recipe-food-nutrition-v1.p.rapidapi.com/recipes/{id}/information"

# Foursquare API Key
FOURSQUARE_API_KEY = 'fsq3JzRFpubCHA54Lu0lL5eVh1Adu9t7K0BeM7DiJiqsGig='  # Replace with your Foursquare API key

# Create a new ChatBot instance (you can keep this if you want to use ChatterBot for fallback)
chatbot = ChatBot(
    'MyBot',
    storage_adapter='chatterbot.storage.SQLStorageAdapter',
    database_uri='sqlite:///database.sqlite3'
)

# Function to handle math queries using WolframAlpha with show steps
def handle_math_and_factual_query(user_input):
    """
    Handles math queries by using WolframAlpha, including options for showing steps.
    """

    try:
        res = wolfram_math_client.query(user_input)
        answer = next(res.results).text
        logger.debug(f"answer is: {answer}")
        return answer
    except StopIteration:
        logger.debug("WolframAlpha did not return a result for math query.")
        return "I couldn't calculate that."


# Function to handle conversational queries using Wit.ai
def handle_conversational_query(user_input):
    logger.info("I am above headers")
    headers = {
        'Authorization': 'Bearer SDE4C7U6GI2NQ7LQKZYQFLUGB6DODMXJ',  # API key as a string
        'Content-Type': 'application/json'
    }

    logger.info("I am below headers")

    response = requests.get(
        'https://api.wit.ai/message',
        headers=headers,
        params={'q': user_input}
    )
    if response.status_code == 200:
        logger.info("I am in if loop of handle_conversational_query")
        wit_response = response.json()
        # Extract the response from Wit.ai
        logger.info(f"Wit.ai response: {wit_response}")
        return wit_response.get('text', 'Sorry, I couldn\'t understand that.')
    else:
        logger.info("I am in else loop of handle_conversational_query")
        logger.error(f'Error with Wit.ai API call: {response.status_code}, {response.text}')
        return 'Sorry, there was an error processing your request.'
        
# Function to handle places to visit in a specific country using Foursquare API
def handle_places_query(user_input):
    # Extract country name from user_input
    # Example: "places to visit in France" should extract "France"
    country = None
    if 'in' in user_input:
        parts = user_input.split('in')
        if len(parts) > 1:
            country = parts[1].strip()
    print(country)
    if not country:
        return "Please specify a country to find places to visit."

    search_url = "https://api.foursquare.com/v3/places/search"
    querystring = {
        "query": "tourist attractions",
        "near": country,
        "limit": 5  # Adjust limit as needed
    }
    headers = {
        "Authorization": "Bearer fsq3JzRFpubCHA54Lu0lL5eVh1Adu9t7K0BeM7DiJiqsGig="
    }

    response = requests.get(search_url, headers=headers, params=querystring)

    if response.status_code == 200:
        data = response.json()
        places = data.get('results', [])
        if places:
            result = []
            for place in places:
                result.append(f"Name: {place.get('name', 'N/A')}, Address: {place.get('location', {}).get('address', 'N/A')}")
            return "\n".join(result)
        else:
            return "No places found for the specified country."
    else:
        return "Sorry, there was an error retrieving places."

def handle_recipe_query(query):
    headers = {
        'x-rapidapi-key': SPOONACULAR_API_KEY,
        'x-rapidapi-host': 'spoonacular-recipe-food-nutrition-v1.p.rapidapi.com'
    }
    search_params = {
        'query': query
    }
    search_response = requests.get(SPOONACULAR_SEARCH_URL, headers=headers, params=search_params)
    search_data = search_response.json()

    recipes = search_data.get('results', [])
    if recipes:
        recipe_id = recipes[0].get('id')
        if recipe_id:
            detail_response = requests.get(SPOONACULAR_RECIPE_URL.format(id=recipe_id), headers=headers)
            detail_data = detail_response.json()

            title = detail_data.get('title', 'No title available')
            ready_in_minutes = detail_data.get('readyInMinutes', 'N/A')
            servings = detail_data.get('servings', 'N/A')
            ingredients = [f"{ingredient.get('amount', '')} {ingredient.get('unit', '')} {ingredient.get('name', '')}" for ingredient in detail_data.get('extendedIngredients', [])]
            instructions = detail_data.get('instructions', 'No instructions available')

            # Construct formatted response
            response = (
                f"**Recipe**: {title}\n"
                f"**Ready in**: {ready_in_minutes} minutes\n"
                f"**Servings**: {servings}\n"
                f"**Ingredients**:\n" + "\n".join(ingredients) + "\n"
                f"**Instructions**:\n{instructions}"
            )
            return response

    return 'Sorry, I couldn\'t find a recipe for that.'
    
# Initialize Flask app
app = Flask(__name__)

# Flask routes
@app.route('/')
def index():
    logger.debug('Serving index.html')
    return send_from_directory('.', 'index.html')


@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_input = request.json.get('message')
        logger.debug(f'Received message: {user_input}')

        # Handle recipe queries
        if 'recipe' in user_input.lower():
            response = handle_recipe_query(user_input)
        # Handle places to visit queries
        elif 'place' in user_input.lower() or 'visit' in user_input.lower():
            response = handle_places_query(user_input)
        else:
            # Try to handle the query with WolframAlpha first
            response = handle_math_and_factual_query(user_input)

            # If no valid response from WolframAlpha, use Wit.ai
            if response in ["I couldn't calculate that.", None, "", "Sorry, I didn't understand that."]:
                logger.debug('Falling back to Wit.ai.')
                response = handle_conversational_query(user_input)

        return jsonify({'response': response})
    
    except Exception as e:
        logger.error(f'Error processing request: {e}')
        return jsonify({'response': 'Sorry, there was an error processing your request.'})


@app.route('/test')
def test():
    return "Test endpoint is working!"



# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
