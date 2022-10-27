# Tenda Beli Simple Plug Server in Python 3.x by Gough Lui (goughlui.com) modified by JakDOH
# ---------------------------------------------------------------------------
# Provision your plugs in such a way to connect to the IP address that this
# server is running on and the code takes care of the rest, providing a basic
# HTML interface on Port 8080.
#
# Feel free to modify and reuse the code. No warranties are provided - it is
# code done in a night and is very much as "rough" and "hacky" as it gets.
# Quick and dirty, but it does work!
#
# As it runs with HTTP with no authentication, it is not secure and I do not
# recommend running this on a network which may be accesed by untrusted
# parties.
# ---------------------------------------------------------------------------
import socket
import select
import time
import sys
from threading import Thread
try:
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.bind(("", 1821)) # Rendezvous Server
  s.listen()
  t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  t.bind(("", 1822)) # Runtime Server
  t.setblocking(0) # Must be non-blocking or hangs waiting for keepalive to perform toggle
  t.settimeout(200)
  t.listen()
  u = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  u.bind(("",8080)) # HTTP Control Server
  u.listen()
  toggleclients=[] # Clients with a pending toggle request
  plugstates={}    # Dictionary of connected plugs with their switch status : ON/OFF
  plugpowers={}    # Dictionary of connected plugs with their power 
  plugconsume={}    # Dictionary of connected plugs with their overall consumption
  plugconsumeInc={} # Dictionary of connected plugs with their last hour increment consumption
  plugfnames={"10.10.10.120":"TV","10.10.10.122":"PC","10.10.10.121":"Dobíjení"} # Dictionary of Friendly Names for Plugs

  def httphandler(conn,addr): # HTTP Control Thread
    data=conn.recv(4096)
    if data[0] == 71 : # Looking for the G in "GET"
      if str(data).find("toggle") > 0 : # Toggle Command Present
        output = str(data).split("toggle/")[1]
        output = output.split("?")[0]
        try:
          if list(sorted(plugstates.keys()))[int(output)] not in toggleclients : # Add to Toggle List
            toggleclients.append(list(sorted(plugstates.keys()))[int(output)])
        except:
          print("Bad toggle request received at "+str(int(time.time()))+"!")
        reply = bytes("HTTP/1.0 302 Found\nLocation: ../\n","utf8")
      else : # Standard Page Load
        reply = bytes("HTTP/1.0 200 OK\nContent-Type: text/html\n\n","utf8")
        reply += bytes('''<html><head><meta http-equiv="content-type" content="text/html; charset=windows-1252"><meta http-equiv="refresh" content="3"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Tenda Beli Simple Python Controller</title></head><body><h2>Tenda Beli Simple Python Controller</p></h2><p><table border="10"><tbody><tr><td><center><table><tbody><tr><td><center><b>Plugs</b<</center></td><td><center><b>State</b></center></td><td><center><b> Power</b></center></td><td><center><b>Overall Consumption</b></center></td></tr>''',"utf8")
        n = 0
        for p in sorted(plugstates.keys()) :
          reply += bytes('''<tr><td><center><form action="./toggle/'''+str(n)+'''" method="get"><input type="submit" value="''',"utf8")
          if str(p[0]) in plugfnames :
            reply += bytes(plugfnames.get(str(p[0])),"utf8")
          else :
            reply += bytes(str(p[0]),"utf8")
          reply += bytes('''"></form></center></td><td><center>''',"utf8")
          if plugstates.get(p) == "1" :
            reply += bytes("On","utf8")
          elif plugstates.get(p) == "0" :
            reply += bytes("Off","utf8")
          else :
            reply += bytes("Unknown","utf8")
          reply += bytes('''</form></center></td><td><center>''',"utf8")
          reply += bytes(str(plugpowers.get(p)),"utf8")
          #reply += bytes('''</center></td></tr>''',"utf8")
          reply += bytes('''</form></center></td><td><center>''',"utf8")
          try:
            consumeFl =float(plugconsume.get(p))
          except:
            consumeFl = 0.000
          try:
            consumeIncFl =float(plugconsumeInc.get(p))
          except:
            consumeIncFl = 0.000
          reply += bytes(str(consumeIncFl+consumeFl),"utf8")
          reply += bytes('''</center></td></tr>''',"utf8")
          n+=1
        reply += bytes('''<tr><td></td></tr></tbody></table></center></td></tr></tbody></table></p></body></html>''',"utf8")
      conn.sendall(reply)
    else :
      print("Bad HTTP request received at "+str(int(time.time()))+"!")
    conn.close() # If not GET, just close connection

  def plughandler(conn,addr): # Runtime Control Thread
    lpkt=time.time()
    lastPowerReq=time.time()
    lastConsumReq=time.time()
    if addr not in plugstates:
      plugstates.update({addr:-1}) # Add new plug to Dict
      plugconsume.update({addr:"0"})
      plugconsumeInc.update({addr:"0"})
    try:
      data=conn.recv(1024) # Initial Plug Runtime Setup
      reply=bytes.fromhex("24000300001a001d0000000000000000000700010000080001000009000100000a00020064000b000400015180")
      conn.send(reply)
      data=conn.recv(1024)
      while conn :
        r,w,x = select.select([conn],[],[],1) # Wait for incoming data for 1s, else do toggle check
        if len(r) > 0 :
          lpkt=time.time()
          data = conn.recv(1024)
          datapack = data.split(b'$')
          for data_s in datapack:
            if data_s :
              print("[DEBUG] Recieved at",time.ctime()," data:",data_s)
              if data_s[4] == 101 : #0x65
                reply=bytes.fromhex("24000300006600000000000000000000")
                conn.send(reply)
              if data_s[4] == 102 : #0x66
                if len(data_s) == 59:
                  plugstates.update({addr:str(chr(data_s[57]))}) # Update Plug State in Dict
                  #print("[DEBUG] Plug status updated")
              if data_s[4] ==  213: #0xd5
                if len(data_s) > 50:
                  powStr = str(data_s)[-15:-3]
                  index = powStr.rfind(':')
                  powStr = powStr[index+1:]
                  #print("[DEBUG] Power data updated with value:",powStr)
                  plugpowers.update({addr:powStr}) # Update Plug State in Dict
              if data_s[4] == 137 : #0x89
                reply=bytes.fromhex("24000300018c000400000000000000006e756c6c")
                conn.send(reply)
                if len(data_s) > 37:
                  conn.send(reply)
                  consumeRaw = str(data_s[data_s.rfind(b'energy')+10:-4])
                  consumeRaw = consumeRaw.replace("\"", "")
                  consumeRaw = consumeRaw.split(",")
                  dataCnt = len(consumeRaw)
                  if dataCnt % 5 == 0:
                    if dataCnt / 5 == 2:
                        if consumeRaw[1] == consumeRaw[6]:
                            plugconsumeInc.update({addr:consumeRaw[2]})
                        else:
                            plugconsume.update({addr:str(float(plugconsume.get(addr)) + float(consumeRaw[7]))})
                            plugconsumeInc.update({addr:consumeRaw[2]})
                    else:
                        if data_s.rfind(b'ver') > 0:
                          for i in range(0, dataCnt, 5) :
                              plugconsume.update({addr:consumeRaw[i+2]})
        if addr in toggleclients : # Toggle command pending for this plug
          reply=bytes.fromhex("24000300015d000c000000005f0c00007b22616374696f6e223a317d")
          conn.send(reply)
          toggleclients.remove(addr)
        if time.time() > lastPowerReq+30:
          reply=bytes.fromhex("2400030000d500000205000000000000")
          conn.send(reply)
          lastPowerReq = time.time()
        if time.time() > lastConsumReq+330:
          reply=bytes.fromhex("2400030000d500000208000000000000")
          conn.send(reply)
          lastConsumReq = time.time()
        if time.time() > lpkt+101 : # KA interval 98 secs
          print("[DEBUG] Timeout waiting for keepalive from Plug "+str(addr)+" at "+str(int(time.time()))+"!")
          raise Exception("[INFO] Closing Connection")
    except:
      print("Oops!", sys.exc_info()[0], "occurred.")
      print("[ERROR] Lost Connection with Plug "+str(addr)+" at "+str(int(time.time()))+"!")
      plugstates.pop(addr,None) # Remove dead plug from Dict
      while addr in toggleclients :
        toggleclients.remove(addr)
      conn.close()
      print("[INFO] Connection closing due to exception ")
      sys.exit()

  def rzvhandler(conn,addr): # Rendezvous Server Thread
    data=conn.recv(1024) 
    reply=bytes.fromhex("2400020000d2000e0000000000000000001000040a0a0a6d00110002071e")
    #                                                            x.x.x.x.        xxxx   Send Plug to provisioning server (ip/port)
    conn.send(reply)
    conn.close()
    print("[INFO] Plug %s send to provisioning server on 10.10.10.101:1822", addr)

  print("Tenda Beli Simple Plug Server Started!")
  while True: # Main Loop
    r,w,x = select.select([s,t,u],[],[]) # Whatever socket has data
    for v in r :
      if v is s :
        conn, addr = s.accept()
        threadS = Thread(target=rzvhandler,args=(conn,addr),daemon=True)
        threadS.start()
      elif v is t :
        conn, addr = t.accept()
        threadT = Thread(target=plughandler,args=(conn,addr),daemon=True)
        threadT.start()
      elif v is u :
        conn, addr = u.accept()
        threadU = Thread(target=httphandler,args=(conn,addr),daemon=True)
        threadU.start()

except KeyboardInterrupt:
      print("Program terminated manually! Be aware, TCP not closed yet")
      sys.exit()
      raise SystemExit
