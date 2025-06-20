from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.sqlite import JSON
import os
import json
import pandas as pd
import random
from uuid import uuid4

GTZAN_CSV_PATH = "features_30_sec.csv"
gtzan_df = pd.read_csv(GTZAN_CSV_PATH)

print("CSV Filenames (first 10):", gtzan_df['filename'].head(10).tolist())
genre_song_map= {}

print("Found audio files:", os.listdir("static/audio"))

for _, row in gtzan_df.iterrows():
    filename = row['filename']
    genre = row['label']
    audio_path = f"static/audio/{filename}"

    if not os.path.isfile(audio_path):
        continue

    if genre not in genre_song_map:
        genre_song_map[genre] =[]

    genre_song_map[genre].append({
        "title": filename,
        "artist": "Unknown",
        "url": f"http://127.0.0.1:5000/static/audio/{filename}"
    })

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class Playlist(db.Model):
    id= db.Column(db.Integer, primary_key=True)
    username= db.Column(db.String(80), nullable=False)
    name= db.Column(db.String(120), nullable=False)
    songs= db.Column(db.Text, nullable=False)
    share_id = db.Column(db.String(100), unique = True)



@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if (not username) or (not password):
        return jsonify({'message': 'Missing fields'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'User already exists'}), 400
    
    new_user =User(
        username=username,
        password_hash=generate_password_hash(password)
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User created successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user= User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        return jsonify({'message': 'Login successful'}), 200
    return jsonify({'message': 'Invalid username or password'}), 401

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    print("Raw JSON received:", data)
    text_input = data.get('text', '').lower()
    print("Mood input received :", text_input)

    mood_to_genre ={
        "sad" :"blues",
        "happy" : "pop",
        "angry" : "metal",
        "chill": "jazz",
        "focus": "classical",
        "party": "disco",
        "hype": "rock"
    }

    matched_genre = next((g for m, g in mood_to_genre.items() if m in text_input), "pop")
    print("matched_genre: ", matched_genre)

    genre_songs = genre_song_map.get(matched_genre, [])
    print(f" Songs available for genre '{matched_genre}':", len(genre_songs))

    if genre_songs:
        songs = random.sample(genre_songs, k=min(5, len(genre_songs)))
    else:
        songs = []

    print(" Songs being sent to frontend:", [song['title'] for song in songs])
    return jsonify({"songs":songs}), 200

@app.route('/playlist', methods=['POST'])
def save_playlist():
    data= request.get_json()
    username= data.get('username')
    name= data.get('name')
    songs= data.get('songs')
    share_id= str(uuid4())[:8]

    if not username or not name or not songs:
        return jsonify({'message': 'Missing data'}), 400
    
    if not isinstance(songs, list) or not all(isinstance(song, dict)for song in songs):
        return jsonify({'message': 'Songs must be a list of objects'}), 400
    
    new_playlist = Playlist(username=username, name=name, songs=json.dumps(songs), share_id =share_id)
    db.session.add(new_playlist)
    db.session.commit()

    return jsonify({'message': 'Playlist saved successfully' ,
            'share_id': share_id, 'share_url': f'http://localhost:5000/shared/{share_id}'}), 201

@app.route('/playlists', methods=['GET'])
def get_playlists():
    username = request.args.get('username')
    if not username:
        return jsonify({'message': 'Username is required'}), 400
    
    user_playlists = Playlist.query.filter_by(username=username).all()
    result = []
    for playlist in user_playlists:
        result.append({
            'id': playlist.id,
            'name': playlist.name,
            'songs': json.loads(playlist.songs),
            'share_id': playlist.share_id
        })
    return jsonify(result), 200

@app.route('/playlist/<int:playlist_id>', methods=['DELETE'])
def delete_playlist(playlist_id):
    playlist = Playlist.query.get(playlist_id)
    if not playlist:
        return jsonify({'message': 'Playlist not found'}), 404
    
    db.session.delete(playlist)
    db.session.commit()
    return jsonify({'message' : 'Playlist deleted'}), 200

@app.route('/clear_playlists', methods=['POST'])
def clear_playlists():
    Playlist.query.delete()
    db.session.commit()
    return jsonify({'message' : 'All playlists deleted'}), 200

@app.route('/playlist/<int:playlist_id>', methods=['PUT'])
def update_playlist(playlist_id):
    playlist = Playlist.query.get(playlist_id)
    if not playlist:
        return jsonify({'message': 'Playlist not found'}), 404
    
    data = request.get_json()
    name = data.get('name')
    songs = data.get('songs')

    if name:
        playlist.name = name
    if songs:
        if not isinstance(songs, list)or not all(isinstance(song, dict) for song in songs):
            return jsonify({'message': 'Invalid song format'}), 400
        playlist.songs = json.dumps(songs)

    db.session.commit()
    return jsonify({'message' : 'Playlist updated'}), 200

@app.route('/shared/<share_id>', methods=['GET'])
def get_shared_playlist(share_id):
    playlist = Playlist.query.filter_by(share_id=share_id).first()
    if not playlist:
        return jsonify({'message': 'Playlist not found'}), 404
    
    return jsonify({
        'name' : playlist.name,
        'songs': json.loads(playlist.songs),
        'share_id': playlist.share_id
    }), 200


if __name__ =='__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)


