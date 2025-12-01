"""
Basic example demonstrating how to connect to ODIN Market Feed
and subscribe to real-time market data.
"""

import asyncio
from odin_market_feed import ODINMarketFeedClient


async def main():
    # Create client instance
    client = ODINMarketFeedClient()
    
    # Define event handlers
    async def on_open():
        print("✅ WebSocket connection opened successfully!")
        print("📊 Subscribing to market data...")
        
        # Subscribe to LTP touchline for specific scrips
        # Format: "segment_token" (e.g., "1_22" means segment 1, token 22)
        await client.subscribe_ltp_touchline(["1_22", "1_2885"])
    
    def on_message(message):
        """Handle incoming market data messages"""
        print(f"📈 Market Data: {message}")
    
    def on_error(error):
        """Handle errors"""
        print(f"❌ Error: {error}")
    
    def on_close(code, reason):
        """Handle connection close"""
        print(f"🔌 Connection closed: {code} - {reason}")
    
    # Assign event handlers
    client.on_open = on_open
    client.on_message = on_message
    client.on_error = on_error
    client.on_close = on_close
    
    try:
        # Connect to the ODIN Market Feed server
        # Replace with your actual server details
        await client.connect(
            host="your.server.com",  # Replace with actual host
            port=4509,               # Replace with actual port
            is_ssl=False,            # Set to True if using SSL
            user_id="YOUR_USER_ID", # Replace with your user ID
            authentication_key=""    # Add authentication key if required
        )
        
        # Keep the connection alive for 60 seconds
        print("⏳ Keeping connection alive for 60 seconds...")
        await asyncio.sleep(60)
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
    finally:
        # Always disconnect properly
        print("🔌 Disconnecting...")
        await client.disconnect()
        print("✅ Disconnected successfully!")


if __name__ == "__main__":
    print("🚀 Starting ODIN Market Feed Client...")
    asyncio.run(main())
