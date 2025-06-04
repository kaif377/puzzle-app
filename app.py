import os
import random
import logging
import hashlib
import time
from flask import Flask, render_template, request, jsonify, session

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_hydration_secret_key")

# Reward system based on difficulty
REWARDS = {
    'easy': [1, 2, 5, 10, 15, 0, 25],
    'medium': [5, 10, 15, 25, 50, 0, 75],
    'hard': [10, 25, 50, 75, 100, 0, 150],
    'extreme': [25, 50, 100, 150, 200, 0, 500]
}

# Puzzle database with multiple types and difficulties
PUZZLES = {
    'easy': [
        {'question': 'What is 5 + 3?', 'answer': '8', 'type': 'math'},
        {'question': 'What is 12 - 7?', 'answer': '5', 'type': 'math'},
        {'question': 'What is 4 × 3?', 'answer': '12', 'type': 'math'},
        {'question': 'What comes next: 2, 4, 6, 8, ?', 'answer': '10', 'type': 'sequence'},
        {'question': 'If CAT = 3, DOG = 3, what does BIRD = ?', 'answer': '4', 'type': 'logic'},
    ],
    'medium': [
        {'question': 'What is 15 × 7 - 23?', 'answer': '82', 'type': 'math'},
        {'question': 'If x + 5 = 12, what is x?', 'answer': '7', 'type': 'algebra'},
        {'question': 'Complete: 1, 1, 2, 3, 5, 8, ?', 'answer': '13', 'type': 'sequence'},
        {'question': 'I am thinking of a number. When I multiply it by 3 and add 7, I get 25. What is the number?', 'answer': '6', 'type': 'word_problem'},
        {'question': 'In Python, what does len("hello") return?', 'answer': '5', 'type': 'coding'},
    ],
    'hard': [
        {'question': 'What is the square root of 144 + 25?', 'answer': '13', 'type': 'math'},
        {'question': 'If 2^x = 32, what is x?', 'answer': '5', 'type': 'algebra'},
        {'question': 'Complete the pattern: 2, 6, 12, 20, 30, ?', 'answer': '42', 'type': 'sequence'},
        {'question': 'A train travels 120 miles in 2 hours. How many miles per hour?', 'answer': '60', 'type': 'word_problem'},
        {'question': 'In JavaScript, what does [1,2,3].length return?', 'answer': '3', 'type': 'coding'},
        {'question': 'What is the next prime number after 17?', 'answer': '19', 'type': 'logic'},
    ],
    'extreme': [
        {'question': 'What is 17² - 13² + 7³?', 'answer': '631', 'type': 'math'},
        {'question': 'If log₂(x) = 4, what is x?', 'answer': '16', 'type': 'algebra'},
        {'question': 'The sequence follows: f(n) = n³ - n² + n. What is f(5)?', 'answer': '105', 'type': 'sequence'},
        {'question': 'A recursive function: f(0)=1, f(1)=1, f(n)=f(n-1)+f(n-2). What is f(6)?', 'answer': '13', 'type': 'coding'},
        {'question': 'In a room of 23 people, what is the probability (%) that two share a birthday? (Round to nearest integer)', 'answer': '51', 'type': 'logic'},
        {'question': 'What is the 10th term in the sequence where a₁=2 and aₙ=2×aₙ₋₁+1?', 'answer': '1023', 'type': 'sequence'},
    ]
}

def generate_puzzle_hash(puzzle_data, timestamp):
    """Generate a hash for puzzle verification"""
    content = f"{puzzle_data['question']}{puzzle_data['answer']}{timestamp}"
    return hashlib.md5(content.encode()).hexdigest()

def get_random_puzzle(difficulty='easy'):
    """Get a random puzzle based on difficulty"""
    if difficulty not in PUZZLES:
        difficulty = 'easy'
    
    puzzle = random.choice(PUZZLES[difficulty])
    timestamp = int(time.time())
    puzzle_hash = generate_puzzle_hash(puzzle, timestamp)
    
    return {
        'question': puzzle['question'],
        'type': puzzle['type'],
        'difficulty': difficulty,
        'hash': puzzle_hash,
        'timestamp': timestamp,
        'answer': puzzle['answer']  # Will be removed before sending to client
    }

@app.route('/')
def index():
    """Main page route"""
    # Initialize wallet if not exists
    if 'wallet' not in session:
        session['wallet'] = 0
    
    # Initialize user level
    if 'level' not in session:
        session['level'] = 'easy'
    
    # Generate a new puzzle
    puzzle = get_random_puzzle(session['level'])
    session['current_puzzle'] = {
        'hash': puzzle['hash'],
        'timestamp': puzzle['timestamp'],
        'answer': puzzle['answer'],
        'difficulty': puzzle['difficulty']
    }
    
    return render_template('index.html', 
                         wallet_balance=session['wallet'],
                         puzzle_question=puzzle['question'],
                         puzzle_type=puzzle['type'],
                         puzzle_difficulty=puzzle['difficulty'],
                         user_level=session['level'])

@app.route('/check', methods=['POST'])
def check_answer():
    """Backend validation route for answer checking"""
    try:
        # Get the user's answer from the request
        data = request.get_json()
        user_answer = data.get('answer', '').strip()
        puzzle_hash = data.get('hash', '')
        
        # Validate input
        if not user_answer:
            return jsonify({
                'success': False,
                'message': 'Please provide an answer',
                'wallet_balance': session.get('wallet', 0)
            }), 400
        
        # Check if puzzle exists in session
        if 'current_puzzle' not in session:
            return jsonify({
                'success': False,
                'message': 'No active puzzle found. Please refresh the page.',
                'wallet_balance': session.get('wallet', 0)
            }), 400
        
        current_puzzle = session['current_puzzle']
        
        # Verify puzzle hasn't expired (30 minutes max)
        current_time = int(time.time())
        if current_time - current_puzzle['timestamp'] > 1800:
            return jsonify({
                'success': False,
                'message': 'Puzzle has expired. Please refresh for a new puzzle.',
                'wallet_balance': session.get('wallet', 0),
                'refresh_needed': True
            }), 400
        
        # Get correct answer and difficulty
        correct_answer = current_puzzle['answer']
        difficulty = current_puzzle['difficulty']
        
        # Initialize wallet if not exists
        if 'wallet' not in session:
            session['wallet'] = 0
        
        # Check if answer is correct (case-insensitive string comparison)
        if user_answer.lower() == correct_answer.lower():
            # Generate random reward based on difficulty
            reward_list = REWARDS.get(difficulty, REWARDS['easy'])
            reward = random.choice(reward_list)
            session['wallet'] += reward
            
            # Level progression logic
            old_level = session.get('level', 'easy')
            new_level = check_level_progression(session['wallet'])
            session['level'] = new_level
            
            # Generate new puzzle for next attempt
            next_puzzle = get_random_puzzle(new_level)
            session['current_puzzle'] = {
                'hash': next_puzzle['hash'],
                'timestamp': next_puzzle['timestamp'],
                'answer': next_puzzle['answer'],
                'difficulty': next_puzzle['difficulty']
            }
            
            level_up_message = ""
            if new_level != old_level:
                level_up_message = f" 🎉 Level up! You're now on {new_level.upper()} difficulty!"
            
            return jsonify({
                'success': True,
                'message': f'Correct! You earned {reward} hydration points!{level_up_message}',
                'reward': reward,
                'wallet_balance': session['wallet'],
                'new_puzzle': {
                    'question': next_puzzle['question'],
                    'type': next_puzzle['type'],
                    'difficulty': next_puzzle['difficulty']
                },
                'level_changed': new_level != old_level,
                'new_level': new_level
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Incorrect! Try again or refresh for a new puzzle.',
                'wallet_balance': session['wallet']
            })
            
    except Exception as e:
        app.logger.error(f"Error in check_answer: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred. Please try again.',
            'wallet_balance': session.get('wallet', 0)
        }), 500

def check_level_progression(wallet_balance):
    """Determine user level based on wallet balance"""
    if wallet_balance >= 1000:
        return 'extreme'
    elif wallet_balance >= 500:
        return 'hard'
    elif wallet_balance >= 100:
        return 'medium'
    else:
        return 'easy'

@app.route('/new_puzzle', methods=['POST'])
def new_puzzle():
    """Generate a new puzzle"""
    try:
        data = request.get_json()
        difficulty = data.get('difficulty', session.get('level', 'easy'))
        
        if difficulty not in PUZZLES:
            difficulty = 'easy'
        
        puzzle = get_random_puzzle(difficulty)
        session['current_puzzle'] = {
            'hash': puzzle['hash'],
            'timestamp': puzzle['timestamp'],
            'answer': puzzle['answer'],
            'difficulty': puzzle['difficulty']
        }
        
        return jsonify({
            'success': True,
            'puzzle': {
                'question': puzzle['question'],
                'type': puzzle['type'],
                'difficulty': puzzle['difficulty'],
                'hash': puzzle['hash']
            }
        })
        
    except Exception as e:
        app.logger.error(f"Error in new_puzzle: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error generating new puzzle'
        }), 500

@app.route('/reset')
def reset_wallet():
    """Reset wallet for testing purposes"""
    session['wallet'] = 0
    return jsonify({
        'success': True,
        'message': 'Wallet reset successfully',
        'wallet_balance': 0
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
