import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import uuid

class TodoService:
    def __init__(self):
        self.data_dir = 'data'
        self.todos_file = os.path.join(self.data_dir, 'todos.json')
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """Ensure the data directory and todos file exist"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        if not os.path.exists(self.todos_file):
            with open(self.todos_file, 'w') as f:
                json.dump([], f)
    
    def _load_todos(self) -> List[Dict]:
        """Load todos from JSON file"""
        try:
            with open(self.todos_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_todos(self, todos: List[Dict]):
        """Save todos to JSON file"""
        with open(self.todos_file, 'w') as f:
            json.dump(todos, f, indent=2, default=str)
    
    def create_todo(self, title: str, description: str = "") -> Dict:
        """Create a new todo note"""
        todo = {
            'id': str(uuid.uuid4()),
            'title': title,
            'description': description,
            'completed': False,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        todos = self._load_todos()
        todos.append(todo)
        self._save_todos(todos)
        
        return todo
    
    def get_all_todos(self) -> List[Dict]:
        """Get all todos"""
        return self._load_todos()
    
    def get_active_todos(self) -> List[Dict]:
        """Get all non-completed todos"""
        todos = self._load_todos()
        return [todo for todo in todos if not todo.get('completed', False)]
    
    def get_todo_by_id(self, todo_id: str) -> Optional[Dict]:
        """Get a specific todo by ID"""
        todos = self._load_todos()
        return next((todo for todo in todos if todo['id'] == todo_id), None)
    
    def update_todo(self, todo_id: str, title: str = None, description: str = None) -> bool:
        """Update a todo's title and/or description"""
        todos = self._load_todos()
        
        for todo in todos:
            if todo['id'] == todo_id:
                if title is not None:
                    todo['title'] = title
                if description is not None:
                    todo['description'] = description
                todo['updated_at'] = datetime.now().isoformat()
                self._save_todos(todos)
                return True
        
        return False
    
    def delete_todo(self, todo_id: str) -> bool:
        """Delete a todo permanently"""
        todos = self._load_todos()
        original_length = len(todos)
        
        todos = [todo for todo in todos if todo['id'] != todo_id]
        
        if len(todos) < original_length:
            self._save_todos(todos)
            return True
        
        return False
    
    def get_todo_stats(self) -> Dict:
        """Get statistics about todos"""
        todos = self._load_todos()
        total = len(todos)
        completed = sum(1 for todo in todos if todo.get('completed', False))
        active = total - completed
        
        return {
            'total': total,
            'active': active,
            'completed': completed
        } 