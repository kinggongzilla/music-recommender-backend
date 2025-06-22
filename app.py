from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy # type: ignore
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.sqlite import JSON
import json
from uuid import uuid4
import requests

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

class LikedSong(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(80), nullable = False)
    title = db.Column(db.String(120), nullable = False)
    artist = db.Column(db.String(120), default="Unknown")
    url = db.Column(db.String(255), nullable = False)



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

    if not text_input:
        return jsonify({'message' : 'No text input provided'}), 400

    try:
        response = requests.post(
            "http://localhost:5000/find_similar_audio",
            json ={"text": text_input}
        )

        ai_results = response.json().get("results", [])

        songs = []
        for r in ai_results:
            songs.append({
                "title" : r["filename"],
                "artist": "Unknown",
                "url": r["full_path"]
            })
        return jsonify({"songs":songs}), 200
    
    except Exception as e:
        return jsonify({'message': 'Error calling AI API', 'error' : str(e)}), 500

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

@app.route('/like', methods=['POST'])
def like_song():
    data = request.get_json()
    username = data.get('username')
    title = data.get('title')
    artist = data.get('artist', 'Unknown')
    url = data.get('url')

    if not username or not title or not url:
        return jsonify({'message' : 'Missing fields'}), 400
    
    liked = LikedSong(username=username, title=title, artist=artist, url=url)
    db.session.add(liked)
    db.session.commit()
    return jsonify({'message' : 'Song liked!'}), 201

@app.route('/likes', methods =['GET'])
def get_likes():
    username = request.args.get('username')
    if not username:
        return jsonify({'message' : 'Username is required'}), 400
    
    liked = LikedSong.query.filter_by(username=username).all()
    result=[{
        'title': song.title,
        'artist': songs.artist,
        'url': song.url
    } for song in liked]

    return jsonify(result), 200


if __name__ =='__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)


