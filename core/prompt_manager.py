"""
Prompt Manager - Manages prompt versions, tracks performance, and learns from feedback
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

PROMPTS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'prompts', 'prompts.json')


class PromptManager:
    def __init__(self):
        self.prompts_file = PROMPTS_FILE
        self.data = self._load_prompts()

    def _load_prompts(self) -> dict:
        """Load prompts from JSON file"""
        if os.path.exists(self.prompts_file):
            with open(self.prompts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"version": "1.0.0", "prompts": {}, "learnings": []}

    def _save_prompts(self):
        """Save prompts to JSON file"""
        self.data['last_updated'] = datetime.now().isoformat()
        with open(self.prompts_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get_active_prompt(self) -> Dict[str, Any]:
        """Get the currently active prompt configuration"""
        active_id = self.data.get('active_prompt')
        if active_id and active_id in self.data['prompts']:
            return self.data['prompts'][active_id]

        # Fallback to first active prompt
        for prompt in self.data['prompts'].values():
            if prompt.get('status') == 'active':
                return prompt

        raise ValueError("No active prompt found")

    def get_prompt_by_id(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific prompt by ID"""
        return self.data['prompts'].get(prompt_id)

    def create_prompt(
        self,
        prompt_id: str,
        name: str,
        prompt_text: str,
        settings: dict,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Create a new prompt version"""
        new_prompt = {
            "id": prompt_id,
            "name": name,
            "status": "testing",
            "created_at": datetime.now().isoformat(),
            "prompt": prompt_text,
            "settings": settings,
            "results": {
                "total_generations": 0,
                "approved": 0,
                "rejected": 0,
                "approval_rate": 0
            },
            "notes": notes
        }

        self.data['prompts'][prompt_id] = new_prompt
        self._save_prompts()
        return new_prompt

    def activate_prompt(self, prompt_id: str):
        """Set a prompt as the active production prompt"""
        if prompt_id not in self.data['prompts']:
            raise ValueError(f"Prompt {prompt_id} not found")

        # Deactivate all other prompts
        for pid, prompt in self.data['prompts'].items():
            if prompt.get('status') == 'active':
                prompt['status'] = 'inactive'

        self.data['prompts'][prompt_id]['status'] = 'active'
        self.data['active_prompt'] = prompt_id
        self._save_prompts()

    def deprecate_prompt(self, prompt_id: str, reason: str):
        """Deprecate a prompt with reason"""
        if prompt_id not in self.data['prompts']:
            raise ValueError(f"Prompt {prompt_id} not found")

        prompt = self.data['prompts'][prompt_id]
        prompt['status'] = 'deprecated'
        prompt['deprecated_at'] = datetime.now().isoformat()
        prompt['deprecation_reason'] = reason
        self._save_prompts()

    def record_generation(self, prompt_id: str, approved: bool):
        """Record a generation result for a prompt"""
        if prompt_id not in self.data['prompts']:
            return

        prompt = self.data['prompts'][prompt_id]
        results = prompt['results']

        results['total_generations'] += 1
        if approved:
            results['approved'] += 1
        else:
            results['rejected'] += 1

        # Calculate approval rate
        if results['total_generations'] > 0:
            results['approval_rate'] = round(
                (results['approved'] / results['total_generations']) * 100, 1
            )

        self._save_prompts()

    def add_learning(self, lesson: str, severity: str = "info"):
        """Add a learning from experience"""
        learning = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "lesson": lesson,
            "severity": severity  # critical, high, medium, info
        }
        self.data['learnings'].append(learning)
        self._save_prompts()

    def get_learnings(self, severity: Optional[str] = None) -> list:
        """Get all learnings, optionally filtered by severity"""
        learnings = self.data.get('learnings', [])
        if severity:
            learnings = [l for l in learnings if l.get('severity') == severity]
        return learnings

    def get_statistics(self) -> dict:
        """Get overall statistics across all prompts"""
        total_gens = 0
        total_approved = 0
        total_rejected = 0

        for prompt in self.data['prompts'].values():
            results = prompt.get('results', {})
            total_gens += results.get('total_generations', 0)
            total_approved += results.get('approved', 0)
            total_rejected += results.get('rejected', 0)

        return {
            "total_generations": total_gens,
            "total_approved": total_approved,
            "total_rejected": total_rejected,
            "overall_approval_rate": round((total_approved / total_gens * 100), 1) if total_gens > 0 else 0,
            "active_prompt": self.data.get('active_prompt'),
            "total_prompts": len(self.data['prompts']),
            "total_learnings": len(self.data.get('learnings', []))
        }

    def list_prompts(self, status: Optional[str] = None) -> list:
        """List all prompts, optionally filtered by status"""
        prompts = list(self.data['prompts'].values())
        if status:
            prompts = [p for p in prompts if p.get('status') == status]
        return prompts


if __name__ == "__main__":
    # Test
    pm = PromptManager()

    print("Active Prompt:")
    active = pm.get_active_prompt()
    print(f"  ID: {active['id']}")
    print(f"  Name: {active['name']}")
    print(f"  Approval Rate: {active['results']['approval_rate']}%")

    print("\nStatistics:")
    stats = pm.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\nLearnings:")
    for learning in pm.get_learnings():
        print(f"  [{learning['severity'].upper()}] {learning['lesson']}")
