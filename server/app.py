"""
AgentHub API Server

A Flask REST API for the shared agent registry.
Enables users to register, discover, and manage AI agents.
"""

import json
from flask import Flask, request, jsonify
from flask_cors import CORS

from models import Agent, LifecycleState, init_db, SessionLocal

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from CLI

# Initialize database on startup
init_db()


# ============================================================================
# Health Check
# ============================================================================

@app.route("/", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "AgentHub API",
        "version": "0.1.0"
    })


# ============================================================================
# Agent CRUD Operations
# ============================================================================

@app.route("/api/agents", methods=["POST"])
def register_agent():
    """Register a new agent."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Validate required fields
    required = ["name", "version", "description", "author"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400
    
    db = SessionLocal()
    try:
        # Check if agent already exists
        existing = db.query(Agent).filter(Agent.name == data["name"]).first()
        if existing:
            return jsonify({"error": f"Agent '{data['name']}' already exists"}), 409
        
        # Create new agent
        agent = Agent(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            author=data["author"],
            capabilities=json.dumps(data.get("capabilities", [])),
            protocols=json.dumps(data.get("protocols", [])),
            permissions=json.dumps(data.get("permissions", [])),
            lifecycle_state=data.get("lifecycle_state", LifecycleState.ACTIVE.value),
        )
        
        db.add(agent)
        db.commit()
        db.refresh(agent)
        
        return jsonify(agent.to_dict()), 201
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/api/agents", methods=["GET"])
def list_agents():
    """List all agents, optionally filtered by state."""
    state = request.args.get("state")
    limit = request.args.get("limit", 100, type=int)
    
    db = SessionLocal()
    try:
        query = db.query(Agent)
        
        if state:
            query = query.filter(Agent.lifecycle_state == state)
        
        agents = query.limit(limit).all()
        return jsonify([agent.to_dict() for agent in agents])
        
    finally:
        db.close()


@app.route("/api/agents/<name>", methods=["GET"])
def get_agent(name: str):
    """Get a specific agent by name."""
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.name == name).first()
        
        if not agent:
            return jsonify({"error": f"Agent '{name}' not found"}), 404
        
        return jsonify(agent.to_dict())
        
    finally:
        db.close()


@app.route("/api/agents/<name>", methods=["PATCH"])
def update_agent(name: str):
    """Update an agent's lifecycle state."""
    data = request.get_json()
    
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.name == name).first()
        
        if not agent:
            return jsonify({"error": f"Agent '{name}' not found"}), 404
        
        # Update allowed fields
        if "lifecycle_state" in data:
            agent.lifecycle_state = data["lifecycle_state"]
        
        db.commit()
        db.refresh(agent)
        
        return jsonify(agent.to_dict())
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/api/agents/<name>", methods=["DELETE"])
def delete_agent(name: str):
    """Remove an agent from the registry."""
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.name == name).first()
        
        if not agent:
            return jsonify({"error": f"Agent '{name}' not found"}), 404
        
        db.delete(agent)
        db.commit()
        
        return jsonify({"message": f"Agent '{name}' deleted"})
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# Search
# ============================================================================

@app.route("/api/search", methods=["GET"])
def search_agents():
    """Search agents by capability or text query."""
    capability = request.args.get("capability")
    query = request.args.get("q")
    limit = request.args.get("limit", 50, type=int)
    
    db = SessionLocal()
    try:
        db_query = db.query(Agent).filter(
            Agent.lifecycle_state != LifecycleState.REVOKED.value
        )
        
        if capability:
            # Search in capabilities JSON
            db_query = db_query.filter(
                Agent.capabilities.contains(f'"{capability}"')
            )
        elif query:
            # Full-text search in name and description
            search_pattern = f"%{query}%"
            db_query = db_query.filter(
                (Agent.name.ilike(search_pattern)) |
                (Agent.description.ilike(search_pattern))
            )
        
        agents = db_query.limit(limit).all()
        return jsonify([agent.to_dict() for agent in agents])
        
    finally:
        db.close()


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    
    print(f"🚀 AgentHub API starting on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
