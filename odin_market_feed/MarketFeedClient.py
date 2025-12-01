import asyncio
import websockets
import zlib
import struct
from typing import Optional, Callable, List
from io import BytesIO
from enum import Enum
from datetime import datetime, timedelta


class CompressionStatus(Enum):
    ON = "ON"
    OFF = "OFF"


class MarketData:
    def __init__(self):
        self.mkt_seg_id: int = 0
        self.token: int = 0
        self.lut: int = 0
        self.ltp: int = 0
        self.close_price: int = 0
        self.decimal_locator: int = 0

"""Handles ZLIB compression and decompression"""
class ZLIBCompressor: 
    
    @staticmethod
    def compress(data: bytes) -> bytes:
        """Compress data using ZLIB"""
        return zlib.compress(data, zlib.Z_DEFAULT_COMPRESSION)
    
    @staticmethod
    def uncompress(data: bytes) -> bytes:
        """Uncompress data using ZLIB"""
        uncompData = zlib.decompress(data)
        return uncompData


class FragmentationHandler:
    """Handles message fragmentation and defragmentation"""
    
    MINIMUM_PACKET_SIZE = 5
    PACKET_HEADER_SIZE = 5
    MESSAGE_LENGTH_LENGTH = 5
    
    def __init__(self):
        self.memory_stream = BytesIO()
        self.last_written_index = -1
        self.is_disposed = False
        self.zlib_compressor = ZLIBCompressor()
    
    def fragment_data(self, data: bytes) -> bytes:
        """Fragment and compress data for sending"""
        compressed = self.zlib_compressor.compress(data)
        length_string = str(len(compressed)).zfill(6)
        len_bytes = bytearray(length_string.encode('ascii'))
        len_bytes[0] = 5  # compression flag
        self.header_length = 6
        self.header_char = bytearray(5)
        bytes_to_send = len_bytes + compressed
        return bytes(bytes_to_send)
    
    def defragment(self, data: bytes) -> List[bytes]:
        """Defragment received data"""
        if self.is_disposed:
            return []
        
        # Write data to memory stream
        self.memory_stream.seek(self.last_written_index + 1)
        self.memory_stream.write(data)
        self.last_written_index = self.memory_stream.tell() - 1
        
        return self._defragment_data()
    
    def _defragment_data(self) -> List[bytes]:
        """Internal method to defragment data"""
        parse_done = False
        bytes_parsed = 0
        packet_list = []
        
        self.memory_stream.seek(0)
        
        while (self.memory_stream.tell() < self.last_written_index - self.MINIMUM_PACKET_SIZE 
               and not parse_done):
            
            header = self.memory_stream.read(self.PACKET_HEADER_SIZE + 1)
            if len(header) < self.PACKET_HEADER_SIZE + 1:
                break
            
            packet_size = self._is_length(header)
            
            if packet_size <= 0:
                self.memory_stream.seek(self.memory_stream.tell() - self.PACKET_HEADER_SIZE)
                bytes_parsed += 1
            else:
                current_pos = self.memory_stream.tell()
                if current_pos + packet_size <= self.last_written_index + 1:
                    compress_data = self.memory_stream.read(packet_size)
                    self._defragment_inner_data(compress_data, packet_list)
                    bytes_parsed += self.PACKET_HEADER_SIZE + 1 + packet_size
                else:
                    parse_done = True
        
        self._clear_processed_data(bytes_parsed)
        return packet_list
    
    def _is_length(self, header: bytes) -> int:
        """Check if header contains valid length"""
        if len(header) != self.PACKET_HEADER_SIZE + 1:
            return -1
        
        if header[0] not in [5, 2]:
            return -1
        
        length_str = header[1:6].decode('ascii')
        if not length_str.isdigit():
            return -1
        
        return int(length_str)
    
    def _defragment_inner_data(self, compress_data: bytes, packet_list: List[bytes]):
        """Decompress and add to packet list"""
        try:
            message_data = self.zlib_compressor.uncompress(compress_data)
            packet_count = 0
            while True:
                self.uncompress_msg_length = 0
                self.uncompress_msg_length = self._get_message_length(message_data)
                
                if self.uncompress_msg_length <= 0:
                    message_data = None
                    break
                
                uncompress_bytes = message_data[
                    self.header_length:self.header_length + self.uncompress_msg_length
                ]
                packet_list.append(uncompress_bytes)
                packet_count += 1
                
                remaining_length = len(message_data) - self.uncompress_msg_length - self.header_length
                if remaining_length <= 0:
                    message_data = None
                    break
                
                message_data = message_data[self.uncompress_msg_length + self.header_length:]
            
        except Exception as e:
            print(f"Error decompressing data: {e}")

    def _get_message_length(self, message_data: bytes) -> int:
        """Extract the message length from the message data"""
        if len(message_data) == 0:
            return 0
        
        # Check first byte to determine compression
        if message_data[0] == 5:
            self.is_uncompress = False
        else:
            self.is_uncompress = True
        
        try:
            start_index = 0
            for i in range(1, min(self.header_length, len(message_data))):
                self.header_char[start_index] = message_data[i]
                start_index += 1
            
            # Convert bytes to string and parse as integer
            s_length = self.header_char[:start_index].decode('ascii')
            i_length = int(s_length)
            return i_length
        except Exception:
            return 0        
    
    def _clear_processed_data(self, length: int):
        """Clear processed data from memory stream"""
        if length <= 0:
            return
        
        if length >= self.last_written_index + 1:
            self.last_written_index = -1
            self.memory_stream = BytesIO()
            return
        
        size = (self.last_written_index + 1) - length
        self.memory_stream.seek(length)
        data = self.memory_stream.read(size)
        
        self.memory_stream = BytesIO()
        self.memory_stream.write(data)
        self.last_written_index = size - 1


class ODINMarketFeedClient:
    """WebSocket client for trading/price feed API"""
    
    def __init__(self):
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.compression_status = CompressionStatus.ON
        self.channel_id = "Broadcast"
        self.user_id = ""
        self.is_disposed = False
        self.receive_buffer_size = 8192
        self.frag_handler = FragmentationHandler()
        self.dte_nse = datetime(1980, 1, 1)
        
        # Event callbacks
        self.on_open: Optional[Callable[[], None]] = None
        self.on_message: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_close: Optional[Callable[[int, str], None]] = None
        
        self._receive_task: Optional[asyncio.Task] = None
    
    def set_compression(self, enabled: bool):
        """Enable or disable compression"""
        self.compression_status = CompressionStatus.ON if enabled else CompressionStatus.OFF
    
    async def connect(self, host: str, port: int,  user_id: str, use_ssl: bool = False, api_key: str =""):
        """Connect to WebSocket server"""
    
        # Validate host
        if not isinstance(host, str):
            raise TypeError(f"host must be a string, got {type(host).__name__}")
        if not host or not host.strip():
            raise ValueError("host cannot be empty")
        if len(host) > 253:  # Max DNS hostname length
            raise ValueError("host exceeds maximum length of 253 characters")
        
        # Validate port
        if not isinstance(port, int):
            raise TypeError(f"port must be an integer, got {type(port).__name__}")
        if not (1 <= port <= 65535):
            raise ValueError(f"port must be between 1 and 65535, got {port}")
        
        # Validate use_ssl
##        if not isinstance(use_ssl, bool):
##            raise TypeError(f"use_ssl must be a boolean, got {type(use_ssl).__name__}")
        
        # Validate user_id
        if not isinstance(user_id, str):
            raise TypeError(f"user_id must be a string, got {type(user_id).__name__}")
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        if len(user_id) > 12:  # Reasonable max length
            raise ValueError("user_id exceeds maximum length of 12 characters")
    
        
        self.user_id = user_id
        protocol = "wss" if use_ssl else "ws"
        url = f"{protocol}://{host}:{port}"
        
        try:
            self.websocket = await websockets.connect(url)
            print("Connected")
            
            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_messages())
            
            # Assuming formatTime is a method in your class
            current_time = self.format_time(datetime.now())

            password = "68="
            if api_key and api_key.strip() != "":
                password = f"68={api_key}|401=2"

            # Send login message
            login_msg = f"63=FT3.0|64=101|65=74|66={current_time}|67={self.user_id}|{password}"

            # Send login message
            # login_msg = (f"63=FT3.0|64=101|65=74|66=14:59:22|67={self.user_id}|"
            #             f"68=|4=|400=0|396=HO|51=4|395=127.0.0.1")

            await self.send_message(login_msg)
            
            if self.on_open:
                await self.on_open()
                
        except Exception as e:
            error_msg = f"Connection failed: {str(e)}"
            if self.on_error:
                self.on_error(error_msg)
            raise
    
    def format_time(self, dt):
        """Format datetime to desired format"""
        return dt.strftime("%H:%M:%S")

    async def disconnect(self):
        """Disconnect from WebSocket server"""
        #and not self.websocket.closed:
        if self.websocket: 
            await self.websocket.close()
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

    async def subscribe_touchline(self,token_list: List[str],response_type: str = "0", ltp_change_only: bool = False) -> None:
        """
        Send Touchline request for market data
        
        Args:
            token_list: List of tokens to subscribe (1_22, 1_2885)
            response_type: 1 = Touchline with fixed length native data, 0 = Normal touchline
            ltp_change_only: Send Touchline Response on LTP change if True
        """
        if not token_list or len(token_list) == 0:
            if self.on_error:
                self.on_error("Token list cannot be null or empty.")
            return
        
        if response_type not in ["0", "1"]:
            if self.on_error:
                self.on_error("Invalid response type passed. Valid values are 0 or 1")
            return
        
        str_token_to_subscribe = ""
        
        for item in token_list:
            if self.is_null_or_whitespace(item):
                continue
            
            parts = item.split('_')
            
            if len(parts) != 2:
                if self.on_error:
                    self.on_error(f"Invalid token format: '{item}'. Expected format: 'MarketSegmentID_Token'.")
                continue
            
            try:
                market_segment_id = int(parts[0])
                token = int(parts[1])
            except ValueError:
                if self.on_error:
                    self.on_error(f"Invalid token format: '{item}'. Expected format: 'MarketSegmentID_Token'.")
                continue
            
            str_token_to_subscribe += f"1={market_segment_id}$7={token}|"
        
        str_response_type = ""
        if response_type == "1":
            str_response_type = "49=1"
        
        s_lt_change_only = "200=1" if ltp_change_only else "200=0"
        
        if len(str_token_to_subscribe) > 0:
            current_time = self.format_time(datetime.now())
            
            if str_response_type != "":
                tl_request = f"63=FT3.0|64=206|65=84|66={current_time}|{str_response_type}|{s_lt_change_only}|{str_token_to_subscribe}230=1"
            else:
                tl_request = f"63=FT3.0|64=206|65=84|66={current_time}|{s_lt_change_only}|{str_token_to_subscribe}230=1"
            
            await self.send_message(tl_request)
            print(f"Subscribed to touchline tokens: {', '.join(token_list)}")
        else:
            if self.on_error:
                self.on_error("No valid tokens found to subscribe.")
    
    async def subscribe_ltp_touchline(self, token_list: List[str]) -> None:
        """
        Send LTP Touchline request for market data
        
        Args:
            token_list: List of tokens to subscribe (1_22, 1_2885)
        """
        if not token_list or len(token_list) == 0:
            if self.on_error:
                self.on_error("Token list cannot be null or empty.")
            return
        
        str_token_to_subscribe = ""
        
        for item in token_list:
            if self.is_null_or_whitespace(item):
                continue
            
            parts = item.split('_')
            
            if len(parts) != 2:
                if self.on_error:
                    self.on_error(f"Invalid token format: '{item}'. Expected format: 'MarketSegmentID_Token'.")
                continue
            
            try:
                market_segment_id = int(parts[0])
                token = int(parts[1])
            except ValueError:
                if self.on_error:
                    self.on_error(f"Invalid token format: '{item}'. Expected format: 'MarketSegmentID_Token'.")
                continue
            
            str_token_to_subscribe += f"1={market_segment_id}$7={token}|"
        
        if len(str_token_to_subscribe) > 0:
            current_time = self.format_time(datetime.now())
            tl_request = f"63=FT3.0|64=347|65=84|66={current_time}|{str_token_to_subscribe}230=1"
            await self.send_message(tl_request)
            print(f"Subscribed to LTP touchline tokens: {', '.join(token_list)}")
        else:
            if self.on_error:
                self.on_error("No valid tokens found to subscribe.")
    
    async def unsubscribe_ltp_touchline(self, token_list: List[str]) -> None:
        """
        Unsubscribe from LTP Touchline
        
        Args:
            token_list: List of tokens to unsubscribe (1_22, 1_2885)
        """
        if not token_list or len(token_list) == 0:
            if self.on_error:
                self.on_error("Token list cannot be null or empty.")
            return
        
        str_token_to_subscribe = ""
        
        for item in token_list:
            if self.is_null_or_whitespace(item):
                continue
            
            parts = item.split('_')
            
            if len(parts) != 2:
                if self.on_error:
                    self.on_error(f"Invalid token format: '{item}'. Expected format: 'MarketSegmentID_Token'.")
                continue
            
            try:
                market_segment_id = int(parts[0])
                token = int(parts[1])
            except ValueError:
                if self.on_error:
                    self.on_error(f"Invalid token format: '{item}'. Expected format: 'MarketSegmentID_Token'.")
                continue
            
            str_token_to_subscribe += f"1={market_segment_id}$7={token}|"
        
        if len(str_token_to_subscribe) > 0:
            current_time = self.format_time(datetime.now())
            tl_request = f"63=FT3.0|64=347|65=84|66={current_time}|{str_token_to_subscribe}230=2"
            await self.send_message(tl_request)
            print(f"Unsubscribed to LTP touchline tokens: {', '.join(token_list)}")
        else:
            if self.on_error:
                self.on_error("No valid tokens found to subscribe.")
    
    async def subscribe_pause_resume(self, is_pause: bool) -> None:
        """
        Pause or resume the broadcast subscription
        
        Args:
            is_pause: True to pause, False to resume
        """
        s_is_pause = "230=1" if is_pause else "230=2"
        current_time = self.format_time(datetime.now())
        tl_request = f"63=FT3.0|64=106|65=84|66={current_time}|{s_is_pause}"
        
        await self.send_message(tl_request)
        print(f"{'Pause' if is_pause else 'Resume'} request Sent")
    
    # Helper methods
    def is_null_or_whitespace(self, s: str) -> bool:
        """Check if string is None, empty, or whitespace"""
        return not s or s.strip() == ""
    
    def format_time(self, date: datetime) -> str:
        """Format datetime to HH:MM:SS"""
        return date.strftime("%H:%M:%S")
    
    async def subscribe_touchlineold(self, token_list: List[str]):
        """
        Subscribe to touchline for the provided tokens.
        
        Args:
            token_list: List of tokens in format 'MarketSegmentID_Token'
        """
        if not token_list or len(token_list) == 0:
            if self.on_error:
                self.on_error("Token list cannot be null or empty.")
            return
        
        str_token_to_subscribe = ""
        
        for item in token_list:
            if not item or item.strip() == "":
                continue
            
            parts = item.split('_')
            if len(parts) != 2:
                if self.on_error:
                    self.on_error(f"Invalid token format: '{item}'. Expected format: 'MarketSegmentID_Token'.")
                continue
            
            try:
                market_segment_id = int(parts[0])
                token = int(parts[1])
            except ValueError:
                if self.on_error:
                    self.on_error(f"Invalid token format: '{item}'. Expected format: 'MarketSegmentID_Token'.")
                continue
            
            str_token_to_subscribe += f"1={market_segment_id}$7={token}|"
        
        if str_token_to_subscribe:
            current_time = datetime.now().strftime('%H:%M:%S')
            tl_request = f"63=FT3.0|64=206|65=84|66={current_time}|4=|{str_token_to_subscribe}230=1"
            await self.send_message(tl_request)
            print(f"Subscribed to touchline tokens: {', '.join(token_list)}")
        else:
            if self.on_error:
                self.on_error("No valid tokens found to subscribe.")


    async def unsubscribe_touchline(self, token_list: List[str]):
        """
        Unsubscribe from touchline for the provided tokens.
        
        Args:
            token_list: List of tokens in format 'MarketSegmentID_Token'
        """
        if not token_list or len(token_list) == 0:
            if self.on_error:
                self.on_error("Token list cannot be null or empty.")
            return
        
        str_token_to_subscribe = ""
        
        for item in token_list:
            if not item or item.strip() == "":
                continue
            
            parts = item.split('_')
            if len(parts) != 2:
                if self.on_error:
                    self.on_error(f"Invalid token format: '{item}'. Expected format: 'MarketSegmentID_Token'.")
                continue
            
            try:
                market_segment_id = int(parts[0])
                token = int(parts[1])
            except ValueError:
                if self.on_error:
                    self.on_error(f"Invalid token format: '{item}'. Expected format: 'MarketSegmentID_Token'.")
                continue
            
            str_token_to_subscribe += f"1={market_segment_id}$7={token}|"
        
        if str_token_to_subscribe:
            current_time = datetime.now().strftime('%H:%M:%S')
            tl_request = f"63=FT3.0|64=206|65=84|66={current_time}|4=|{str_token_to_subscribe}230=2"
            await self.send_message(tl_request)
            print(f"Unsubscribed from touchline tokens: {', '.join(token_list)}")
        else:
            if self.on_error:
                self.on_error("No valid tokens found to unsubscribe.")


    async def subscribe_best_five(self, token: str, market_segment_id: int):
        """
        Subscribe to Market Depth (Best Five) for the provided token and market segment.
        
        Args:
            token: Token identifier
            market_segment_id: Market segment ID
        """
        if not token or token.strip() == "":
            if self.on_error:
                self.on_error("Token cannot be null or empty.")
            return
        
        if market_segment_id <= 0:
            if self.on_error:
                self.on_error("Invalid MarketSegment.")
            return
        
        current_time = datetime.now().strftime('%H:%M:%S')
        tl_request = f"63=FT3.0|64=127|65=84|66={current_time}|1={market_segment_id}|7={token}|230=1"
        await self.send_message(tl_request)
        print(f"Subscribed to BestFive tokens: {token}, MarketSegmentId: {market_segment_id}")


    async def unsubscribe_best_five(self, token: str, market_segment_id: int):
        """
        Unsubscribe from Market Depth (Best Five) for the provided token and market segment.
        
        Args:
            token: Token identifier
            market_segment_id: Market segment ID
        """
        if not token or token.strip() == "":
            if self.on_error:
                self.on_error("Token cannot be null or empty.")
            return
        
        if market_segment_id <= 0:
            if self.on_error:
                self.on_error("Invalid MarketSegment.")
            return
        
        current_time = datetime.now().strftime('%H:%M:%S')
        tl_request = f"63=FT3.0|64=127|65=84|66={current_time}|1={market_segment_id}|7={token}|230=2"
        await self.send_message(tl_request)
        print(f"Unsubscribed from BestFive tokens: {token}, MarketSegmentId: {market_segment_id}")
    
    async def send_message(self, message: str):
        """Send message to WebSocket server"""
        #or self.websocket.closed
        if not self.websocket :
            raise ConnectionError("WebSocket is not connected")
        
        print(f"Sending Message: {message}")
        packet = self.frag_handler.fragment_data(message.encode('ascii'))
        await self.websocket.send(packet)
    
    async def _receive_messages(self):
        """Receive messages from WebSocket server"""
        try:
            async for message in self.websocket:
                if isinstance(message, bytes):
                    self._response_received(message)
                    
        except asyncio.CancelledError:
            print("Receive task cancelled")
        except Exception as e:
            print(f"Error in receive loop: {str(e)}")
            if self.on_error:
                self.on_error(str(e))
    
    def _response_received(self, data: bytes):
        """Process received response"""
        try:
            arr_data = self.frag_handler.defragment(data)
            for i in range(len(arr_data)):
                #if(arr_data[i] == None) continue
                str_msg = arr_data[i].decode('utf-8', errors='ignore')
                
                # Handle binary market data (|50=)
                if "|50=" in str_msg:
                    data_bytes = arr_data[i]
                    data_index = str_msg.index("|50=") + 4
                    str_new_msg = str_msg[:str_msg.index("|50=") + 1]
                    
                    # Market Segment ID
                    mkt_seg_id = struct.unpack('<I', data_bytes[data_index:data_index + 4])[0]
                    str_new_msg += f"1={mkt_seg_id}|"
                    
                    # Token
                    token = struct.unpack('<I', data_bytes[data_index + 4:data_index + 8])[0]
                    str_new_msg += f"7={token}|"
                    
                    # Last Update Time (LUT)
                    lut_seconds = struct.unpack('<i', data_bytes[data_index + 8:data_index + 12])[0]
                    lut_date = self.dte_nse + timedelta(seconds=lut_seconds)
                    lut = lut_date.strftime("%Y-%m-%d %H%M%S")
                    str_new_msg += f"74={lut}|"
                    
                    # Last Trade Time (LTT)
                    ltt_seconds = struct.unpack('<i', data_bytes[data_index + 12:data_index + 16])[0]
                    ltt_date = self.dte_nse + timedelta(seconds=ltt_seconds)
                    ltt = ltt_date.strftime("%Y-%m-%d %H%M%S")
                    str_new_msg += f"73={ltt}|"
                    
                    # Last Traded Price (LTP)
                    ltp = struct.unpack('<I', data_bytes[data_index + 16:data_index + 20])[0]
                    str_new_msg += f"8={ltp}|"
                    
                    # Buy Quantity (BQty)
                    b_qty = struct.unpack('<I', data_bytes[data_index + 20:data_index + 24])[0]
                    str_new_msg += f"2={b_qty}|"
                    
                    # Buy Price (BPrice)
                    b_price = struct.unpack('<I', data_bytes[data_index + 24:data_index + 28])[0]
                    str_new_msg += f"3={b_price}|"
                    
                    # Sell Quantity (SQty) - Note: Original code has a bug and uses BQty
                    s_qty = struct.unpack('<I', data_bytes[data_index + 28:data_index + 32])[0]
                    str_new_msg += f"5={s_qty}|"  # Original code uses BQty here (appears to be a bug)
                    
                    # Sell Price (SPrice) - Note: Original code has a bug and uses BPrice
                    s_price = struct.unpack('<I', data_bytes[data_index + 32:data_index + 36])[0]
                    str_new_msg += f"6={s_price}|"  # Original code uses BPrice here (appears to be a bug)
                    
                    # Open Price (OPrice) - Note: Original code has a bug and uses BQty
                    o_price = struct.unpack('<I', data_bytes[data_index + 36:data_index + 40])[0]
                    str_new_msg += f"75={o_price}|"  # Original code uses BQty here (appears to be a bug)
                    
                    # High Price (HPrice) - Note: Original code has a bug and uses BPrice
                    h_price = struct.unpack('<I', data_bytes[data_index + 40:data_index + 44])[0]
                    str_new_msg += f"77={h_price}|"  # Original code uses BPrice here (appears to be a bug)
                    
                    # Low Price (LPrice) - Note: Original code has a bug and uses BQty
                    l_price = struct.unpack('<I', data_bytes[data_index + 44:data_index + 48])[0]
                    str_new_msg += f"78={l_price}|"  # Original code uses BQty here (appears to be a bug)
                    
                    # Close Price (CPrice) - Note: Original code has a bug and uses BPrice
                    c_price = struct.unpack('<I', data_bytes[data_index + 48:data_index + 52])[0]
                    str_new_msg += f"76={c_price}|"  # Original code uses BPrice here (appears to be a bug)
                    
                    # Decimal Locator
                    dec_locator = struct.unpack('<I', data_bytes[data_index + 52:data_index + 56])[0]
                    str_new_msg += f"399={dec_locator}|"
                    
                    # Previous Close Price
                    prv_close_price = struct.unpack('<I', data_bytes[data_index + 56:data_index + 60])[0]
                    str_new_msg += f"250={prv_close_price}|"
                    
                    # Indicative Close Price
                    indicative_close_price = struct.unpack('<I', data_bytes[data_index + 60:data_index + 64])[0]
                    str_new_msg += f"88={indicative_close_price}|"
                    
                    str_msg = str_new_msg
                
                if self.on_message:
                    self.on_message(str_msg)
##            for packet in arr_data:
##                message = packet.decode('ascii')
##                
##            arrMsg = self.parse_data(message);
##        
##            for msg in arrMsg:
##                if self.on_message:
##                    self.on_message(msg)
                
        except Exception as e:
            print(f"Error processing response: {e}")
            if self.on_error:
                self.on_error(str(e))

    def parse_data(self,data: str) -> list:

        messages = []
        print(f"Receive parse_data >>>>> {data}")
        while len(data) > 6:
            # Extract length from first 5 characters (skip first char)
            length_str = data[1:6]
            
            try:
                message_length = int(length_str)
            except ValueError:
                # Invalid length, break
                break
            
            # Check if we have a complete message
            total_length = 6 + message_length
            
            if len(data) < total_length:
                # Not enough data yet, wait for more
                break
            
            # Extract the complete message
            full_message = data[1:total_length]
            message_data = data[6:total_length]
            # print(f"Receive message_data {message_data}")
            messages.append(message_data)
            
            # Remove processed message from buffer
            data = data[total_length:]
        
        return messages

    def dispose(self):
        """Dispose resources"""
        if not self.is_disposed:
            if self._receive_task:
                self._receive_task.cancel()
            self.is_disposed = True
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        self.dispose()


# Example usage
# async def main():
#     client = TradingWebSocket()
    
#     # Set up event handlers
#     async def on_open():
#         print("WebSocket opened")
        
#         # Subscribe to touchline
#         #await client.subscribe_touchline(["1_22", "1_2885"])
#         #await client.subscribe_touchline(["1_22", "1_2885"],"0",True)
#         #await client.subscribe_touchline(["1_22", "1_2885"],"1",False)
#         #await client.subscribe_touchline(["1_22", "1_2885"],"1",True)
#         await client.subscribe_ltp_touchline(["1_22", "1_2885"]); 
#         await asyncio.sleep(5)
#         await client.subscribe_pause_resume(True) # type: ignore
#         await asyncio.sleep(5)
#         await client.subscribe_pause_resume(False) # type: ignore
#         await client.unsubscribe_ltp_touchline(["1_22", "1_2885"]); 


#         # Unsubscribe from touchline
#         #await asyncio.sleep(10)
#         #await client.unsubscribe_touchline(["1_22", "1_2885"])

#         # Subscribe to best five (market depth)
#         #await client.subscribe_best_five("22", 1)

#         # Unsubscribe from best five
#         #await asyncio.sleep(10)
#         #await client.unsubscribe_best_five("22", 1)
    
#     def on_message(message):
#         print(f"Received ***: {message}")
    
#     def on_error(error):
#         print(f"Error: {error}")
    
#     def on_close(code, reason):
#         print(f"Closed: {code} - {reason}")
    
#     client.on_open = on_open
#     client.on_message = on_message
#     client.on_error = on_error
#     client.on_close = on_close
    
#     try:
#         await client.connect("172.25.100.43", 4509, False, "PRAJYOT","")
        
#         # Keep connection alive
#         await asyncio.sleep(60)
        
#     finally:
#         await client.disconnect()


# if __name__ == "__main__":
#     asyncio.run(main())
