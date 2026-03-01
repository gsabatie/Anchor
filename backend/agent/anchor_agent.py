from google.adk.agents import Agent

from agent.prompts.system_prompt import SYSTEM_PROMPT
from agent.tools.erp_timer import erp_timer
from agent.tools.hierarchy_builder import hierarchy_builder
from agent.tools.image_generator import image_generator
from agent.tools.reassurance_guard import reassurance_guard
from agent.tools.session_tracker import session_tracker

anchor_agent = Agent(
    model="gemini-2.0-flash",
    name="anchor",
    description="ERP therapy companion agent for OCD support",
    instruction=SYSTEM_PROMPT,
    tools=[
        reassurance_guard,
        hierarchy_builder,
        image_generator,
        erp_timer,
        session_tracker,
    ],
)
