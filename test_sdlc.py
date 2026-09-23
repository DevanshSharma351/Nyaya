import asyncio
from nyaya.agents.extraction import extract
from nyaya.agents.schemas import ExtractionContext
from nyaya.mcda.derive import derive
from nyaya.mcda.sdlc import recommend

async def main():
    text = "QuickBite Logistics is an enterprise delivery-management company attempting to modernize its nationwide depot-routing infrastructure. The board of directors has allocated a generous budget, but management has set a strict, non-negotiable deadline: a fully functioning operational system must be rolled out across regional hubs within 60 to 75 days to capture an upcoming holiday logistics surge. The company has hired a dedicated, highly skilled engineering squad well-versed in domain-driven modeling and modern CASE automated-generation tools. Enterprise stakeholders and depot operations managers are fully committed to attending continuous weekly requirement workshops and review sessions. The system's functional requirements can be cleanly broken down into independent, decoupled services: Vehicle Fleet Tracking, Route Scheduling, Driver Payroll, and Depot Inventory Check-in. While the core business rules for each component are largely understood, management wants to rely heavily on pre-tested internal microservice templates and automated code-generation utilities to prevent building common components from scratch."
    context = ExtractionContext(domain="logistics", jurisdictions=["US"])
    print("Extracting requirements...")
    result = await extract(text, context=context)
    print(f"Extracted {len(result.requirements)} requirements.")
    
    derivation = derive(result.requirements, result.unclear, brief=text)
    ranking = recommend(derivation.factors)
    print("Recommended SDLC:", ranking.recommended.name)
    
if __name__ == "__main__":
    asyncio.run(main())
