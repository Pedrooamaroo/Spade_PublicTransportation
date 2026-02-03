"""Message ontology for the transport system.

Defines performatives used by agents and helper functions
to create messages and log metrics in a standardized way.
"""

from spade.message import Message
import json
from enum import Enum
import datetime


class Performative(str, Enum):
    """List of FIPA performatives used in the system."""
    CFP = "cfp"
    PROPOSE = "propose"
    ACCEPT_PROPOSAL = "accept-proposal"
    REJECT_PROPOSAL = "reject-proposal"
    INFORM = "inform"
    REQUEST = "request"
    REFUSE = "refuse"
    FAILURE = "failure"
    CANCEL = "cancel"

class TransportationOntology:
    """
    Helper functions for message creation and logging.
    Centralizes the format of messages exchanged between agents
    and the logging of metrics to the CSV file.
    """

    @staticmethod
    def create_message(to_jid, performative, content_data, thread_id=None):
        """
        Creates a standardized SPADE message in JSON.
        Defines performative, ontology, language, and JSON body,
        optionally including a conversation thread ID.

        Args:
            to_jid (str): Recipient agent JID.
            performative (Performative): Type of communicative act.
            content_data (dict): Message content in dictionary format.
            thread_id (str | None): Conversation thread identifier.

        Returns:
            Message: SPADE message ready to be sent.
        """
        msg = Message(to=str(to_jid))
        msg.set_metadata("performative", performative)
        msg.set_metadata("ontology", "transport-network-v1")
        msg.set_metadata("language", "json")

        if thread_id:
            msg.thread = str(thread_id)

        msg.body = json.dumps(content_data)
        return msg

    @staticmethod
    def format_cfp(origin, destination, passenger_count):
        """
        Formats content for a CFP (Call For Proposal) ride request.
        Args:
            origin (str): Origin station.
            destination (str): Destination station.
            passenger_count (int): Number of passengers.

        Returns:
            dict: Structured content for CFP.
        """
        return {
            "type": "ride_request",
            "origin": origin,
            "destination": destination,
            "passenger_count": passenger_count,
        }

    @staticmethod
    def format_proposal(vehicle_id, eta, capacity_available, route_plan):
        """
        Formats content for a transport proposal.
        Args:
            vehicle_id (str): Vehicle identifier.
            eta (float | int): Estimated Time of Arrival.
            capacity_available (int): Seats currently available.
            route_plan (list): Proposed route plan.

        Returns:
            dict: Structured content for PROPOSE.
        """
        return {
            "type": "bid",
            "vehicle_id": vehicle_id,
            "eta": eta,
            "capacity": capacity_available,
            "route": route_plan,
        }

    @staticmethod
    def format_disruption(location_edge, severity, description):
        """
        Formats a network disruption alert (e.g., accident).
        Args:
            location_edge (list | tuple): Affected edge [origin, destination].
            severity (str | int): Severity level.
            description (str): Description of the issue.

        Returns:
            dict: Structured content for disruption_alert.
        """
        return {
            "type": "disruption_alert",
            "edge": location_edge,
            "severity": severity,
            "details": description,
        }

    @staticmethod
    def format_breakdown(vehicle_id, location, issue_type):
        """
        Formats a vehicle breakdown alert.
        Args:
            vehicle_id (str): Broken vehicle identifier.
            location (str): Current vehicle location.
            issue_type (str): Type of issue (e.g., engine_fail).

        Returns:
            dict: Structured content for breakdown_alert.
        """
        return {
            "type": "breakdown_alert",
            "vehicle_id": vehicle_id,
            "location": location,
            "issue": issue_type,
        }

    @staticmethod
    def format_status(vehicle_id, location, status, current_load):
        """
        Formats a vehicle status update.
        Args:
            vehicle_id (str): Vehicle identifier.
            location (str): Station/Location where it is.
            status (str): Current status (e.g., moving, idle, broken).
            current_load (int): Number of passengers on board.

        Returns:
            dict: Structured content for status_update.
        """
        return {
            "type": "status_update",
            "vehicle_id": vehicle_id,
            "location": location,
            "status": status,
            "load": current_load,
        }

    @staticmethod
    def log_metric(metric_type, source, target, value, extra_info=""):
        """
        Logs a metric to metrics.csv.
        Format: TIMESTAMP, TYPE, SOURCE, TARGET, VALUE, EXTRA

        Args:
            metric_type (str): Metric type (e.g., PASSENGER_SUCCESS).
            source (str): Event origin (agent or location).
            target (str): Associated target (destination, resource, etc.).
            value (str | int | float): Main metric value.
            extra_info (str, optional): Free text additional info.
        """
        try:
            with open("metrics.csv", "a", encoding="utf-8") as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                line = (
                    f"{timestamp},{metric_type},{source},"
                    f"{target},{value},{extra_info}\n"
                )
                f.write(line)
        except Exception as e:
            print(f"Error writing metric: {e}")