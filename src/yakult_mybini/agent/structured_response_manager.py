"""
Structured Response Manager untuk mengatur urutan response AI yang konsisten.

Urutan response:
1. GREET RESPONSE: Sapaan/pendahuluan dari AI
2. TOOL USAGE: Eksekusi tools dan update status
3. END RESPONSE: Respons final/penutup

Contoh flow:
- User: "Tolong update sistem"
- AI: "Oke, bentar aku update sistemnya" (GREET)
- [Update sistem dijalankan] (TOOL)
- AI: "Udah aku update sistemmu" (END)
"""

from typing import AsyncIterator, Dict, Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass
from loguru import logger


class ResponsePhase(Enum):
    """Phase dalam structured response flow"""
    GREET = "greet"           # Sapaan awal
    TOOL = "tool"             # Eksekusi tools
    END = "end"               # Response final
    COMPLETE = "complete"     # Selesai


@dataclass
class StructuredResponse:
    """Wrapper untuk structured response"""
    phase: ResponsePhase
    content: Union[str, Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None


class StructuredResponseManager:
    """Manager untuk mengatur urutan response yang terstruktur"""
    
    def __init__(self):
        self.current_phase = ResponsePhase.GREET
        self.greeted = False
        self.tools_executed = False
        self.tool_results = []
        self.text_buffer = ""
        self.has_tool_calls = False
        
    def detect_tool_calls(self, stream_item: Union[str, Dict[str, Any]]) -> bool:
        """Detect apakah ada tool calls di stream"""
        if isinstance(stream_item, dict) and stream_item.get("type") == "tool_call_status":
            return True
        return False
    
    def reset(self):
        """Reset state untuk conversation baru"""
        self.current_phase = ResponsePhase.GREET
        self.greeted = False
        self.tools_executed = False
        self.tool_results = []
        self.text_buffer = ""
        self.has_tool_calls = False
    
    async def process_stream(
        self,
        stream: AsyncIterator[Union[str, Dict[str, Any]]],
    ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
        """
        Process stream dengan structured response management.
        
        Flow:
        1. Buffer text sampai kita tau ada tool calls
        2. Yield GREET response text
        3. Pass through TOOL status updates
        4. Yield END response text
        """
        self.reset()
        
        # Phase 1: Buffer text dan detect tool calls
        logger.debug("StructuredResponseManager: Starting GREET phase")
        text_chunks = []
        tool_status_queue = []
        phase_transitioned = False
        
        async for item in stream:
            if isinstance(item, dict) and item.get("type") == "tool_call_status":
                # Ada tool call! Transition ke TOOL phase
                if not phase_transitioned:
                    self.has_tool_calls = True
                    # Yield buffered text sebagai GREET phase
                    if text_chunks:
                        logger.debug(f"StructuredResponseManager: Yielding GREET response ({len(text_chunks)} chunks)")
                        for chunk in text_chunks:
                            yield chunk
                    text_chunks = []
                    phase_transitioned = True
                    self.current_phase = ResponsePhase.TOOL
                    logger.debug("StructuredResponseManager: Transitioned to TOOL phase")
                
                # Queue tool status untuk diproses
                tool_status_queue.append(item)
            else:
                # Text atau non-tool item
                if not phase_transitioned and isinstance(item, str):
                    # Still in GREET phase, buffer text
                    text_chunks.append(item)
                elif isinstance(item, dict) and item.get("type") == "final_tool_results":
                    # Tool results finalized, transition ke END phase
                    if not phase_transitioned:
                        # No tool calls, yield greeted text
                        logger.debug(f"StructuredResponseManager: Yielding GREET response (final, {len(text_chunks)} chunks)")
                        for chunk in text_chunks:
                            yield chunk
                        text_chunks = []
                    
                    # Yield all queued tool status before moving to END
                    for tool_item in tool_status_queue:
                        logger.debug(f"StructuredResponseManager: Yielding TOOL status - {tool_item.get('tool_name')}")
                        yield tool_item
                    tool_status_queue = []
                    
                    # Yield final tool results
                    logger.debug(f"StructuredResponseManager: Yielding final tool results")
                    yield item
                    
                    self.current_phase = ResponsePhase.END
                    logger.debug("StructuredResponseManager: Transitioned to END phase")
                    phase_transitioned = True
                else:
                    # Non-tool item (likely error, etc)
                    if text_chunks and not phase_transitioned:
                        # Yield buffered text first
                        logger.debug(f"StructuredResponseManager: Yielding GREET response before non-text item")
                        for chunk in text_chunks:
                            yield chunk
                        text_chunks = []
                        phase_transitioned = True
                    
                    # Yield tool status queue if we have any
                    if tool_status_queue:
                        for tool_item in tool_status_queue:
                            logger.debug(f"StructuredResponseManager: Yielding TOOL status - {tool_item.get('tool_name')}")
                            yield tool_item
                        tool_status_queue = []
                    
                    # Yield this item
                    yield item
        
        # End of stream: flush any remaining buffers
        if text_chunks:
            logger.debug(f"StructuredResponseManager: Flushing {len(text_chunks)} text chunks at stream end")
            for chunk in text_chunks:
                yield chunk
        
        if tool_status_queue:
            logger.debug(f"StructuredResponseManager: Flushing {len(tool_status_queue)} tool status items at stream end")
            for tool_item in tool_status_queue:
                yield tool_item
        
        if phase_transitioned:
            self.current_phase = ResponsePhase.COMPLETE
        
        logger.debug(f"StructuredResponseManager: Stream processing complete. Has tool calls: {self.has_tool_calls}")
