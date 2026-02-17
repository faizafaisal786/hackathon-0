"""
AI Employee Workflow Management System
======================================

Task Lifecycle Pipeline:
    Inbox → Needs_Action → Plans → Pending_Approval → Approved → Done

Each stage represents a specific phase in task processing.
"""

from enum import Enum
from datetime import datetime
from pathlib import Path

class WorkflowStage(Enum):
    """Defines the workflow stages for task management"""
    INBOX = "Inbox"
    NEEDS_ACTION = "Needs_Action"
    PLANS = "Plans"
    PENDING_APPROVAL = "Pending_Approval"
    APPROVED = "Approved"
    DONE = "Done"

# Define the workflow pipeline sequence
WORKFLOW_PIPELINE = [
    WorkflowStage.INBOX,
    WorkflowStage.NEEDS_ACTION,
    WorkflowStage.PLANS,
    WorkflowStage.PENDING_APPROVAL,
    WorkflowStage.APPROVED,
    WorkflowStage.DONE,
]

class TaskWorkflow:
    """Manages task movement through the workflow pipeline"""
    
    def __init__(self, vault_path):
        """
        Initialize workflow manager
        
        Args:
            vault_path: Path to AI_Employee_Vault directory
        """
        self.vault_path = Path(vault_path)
        self.stages = {stage.value: self.vault_path / stage.value for stage in WorkflowStage}
    
    def get_next_stage(self, current_stage):
        """Get the next stage in the workflow"""
        try:
            current_index = WORKFLOW_PIPELINE.index(current_stage)
            if current_index < len(WORKFLOW_PIPELINE) - 1:
                return WORKFLOW_PIPELINE[current_index + 1]
        except ValueError:
            pass
        return None
    
    def get_previous_stage(self, current_stage):
        """Get the previous stage in the workflow"""
        try:
            current_index = WORKFLOW_PIPELINE.index(current_stage)
            if current_index > 0:
                return WORKFLOW_PIPELINE[current_index - 1]
        except ValueError:
            pass
        return None
    
    def move_task(self, task_file, target_stage):
        """
        Move a task file to a target stage
        
        Args:
            task_file: Path to the task file
            target_stage: WorkflowStage enum value
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            source_path = Path(task_file)
            target_dir = self.stages[target_stage.value]
            target_path = target_dir / source_path.name
            
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)
            
            source_path.rename(target_path)
            return True
        except Exception as e:
            print(f"Error moving task: {e}")
            return False
    
    def log_workflow_action(self, task_name, from_stage, to_stage, action_type="move"):
        """Log workflow actions for audit trail"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {action_type.upper()}: {task_name} | {from_stage.value} → {to_stage.value}\n"
        
        logs_dir = self.vault_path / "Logs"
        if logs_dir.exists():
            log_file = logs_dir / "workflow.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
    
    def get_stage_directory(self, stage):
        """Get the directory path for a specific stage"""
        return self.stages.get(stage.value)

# Workflow stage descriptions
STAGE_DESCRIPTIONS = {
    WorkflowStage.INBOX: "New tasks arrive here, waiting for initial review",
    WorkflowStage.NEEDS_ACTION: "Tasks requiring analysis and decision-making",
    WorkflowStage.PLANS: "Tasks with approved plans ready for execution",
    WorkflowStage.PENDING_APPROVAL: "Completed work awaiting human approval",
    WorkflowStage.APPROVED: "Approved tasks ready for final completion",
    WorkflowStage.DONE: "Completed and archived tasks",
}
