import os
import time
import calendar
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from tqdm.notebook import tqdm
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# 1. AUTENTICACAO E CONFIGURACAO
# ==========================================
import traffic
if not traffic.config.has_section('opensky'):
    traffic.config.add_section('opensky')

traffic.config.set('opensky', 'username', 'bernardo_espiritosanto')
traffic.config.set('opensky', 'password', '!*********!')

from traffic.data import opensky
from openap import FuelFlow, Emission, prop

# ==========================================
# 2. PAINEL DE CONTROLO MENSAL
# ==========================================
ANO_ANALISE = 2025
MES_ANALISE = 7   # MES A EXTRAIR

ultimo_dia_do_mes = calendar.monthrange(ANO_ANALISE, MES_ANALISE)[1]
area_lppt = (-9.7, 38.3, -8.5, 39.5) 

nome_base = "LPPTanalisecomplexatudo"
ficheiro_temporario = f"Temp_{nome_base}_mes{MES_ANALISE:02d}.csv"
ficheiro_final = f"{nome_base}_mes{MES_ANALISE:02d}.csv"

# ==========================================
# 3. FUNCOES DE FISICA E MASSAS
# ==========================================
modelos_ff, modelos_em = {}, {}

def obter_modelos(tipo_icao):
    tipo_icao = str(tipo_icao).upper() if tipo_icao else "A320"
    if tipo_icao in modelos_ff:
        return modelos_ff[tipo_icao], modelos_em[tipo_icao], tipo_icao
    try:
        ff, em = FuelFlow(ac=tipo_icao), Emission(ac=tipo_icao)
        modelos_ff[tipo_icao], modelos_em[tipo_icao] = ff, em
        return ff, em, tipo_icao
    except:
        if "A320" not in modelos_ff:
            modelos_ff["A320"], modelos_em["A320"] = FuelFlow(ac="A320"), Emission(ac="A320")
        return modelos_ff["A320"], modelos_em["A320"], "A320 (Estimado)"

def obter_massa_estimada(tipo_icao):
    if not tipo_icao: return 60000 
    tipo = str(tipo_icao).upper()
    try: return prop.aircraft(tipo)['limits']['MTOW'] * 0.75 
    except:
        if tipo.startswith('A38'): return 350000 * 0.75
        elif tipo.startswith(('A33', 'A34', 'A35', 'B74', 'B76', 'B77', 'B78')): return 180000 * 0.75
        elif tipo.startswith(('E1', 'E7', 'AT', 'DH', 'CR')): return 25000 * 0.75
        else: return 60000 

# ==========================================
# 4. FASE 1: EXTRACAO DO TRAFEGO
# ==========================================
data_inicio = datetime(ANO_ANALISE, MES_ANALISE, 1)
data_final = datetime(ANO_ANALISE, MES_ANALISE, ultimo_dia_do_mes)
data_atual = data_inicio

print(f"INICIO DA EXTRACAO COMPLEXA: {nome_base} - MES {MES_ANALISE:02d}")

if os.path.exists(ficheiro_temporario): 
    os.remove(ficheiro_temporario)

pbar_total = tqdm(total=ultimo_dia_do_mes, desc="PROGRESSO MENSAL", unit="dia")

while data_atual <= data_final:
    fim_bloco = data_atual + timedelta(days=4)
    if fim_bloco > data_final: fim_bloco = data_final + timedelta(days=1)
    
    inicio_str = data_atual.strftime("%Y-%m-%d 00:00")
    fim_str = fim_bloco.strftime("%Y-%m-%d 00:00")
    
    desc_bloco = f"A pedir dados (OpenSky): {data_atual.strftime('%d/%m')} a {fim_bloco.strftime('%d/%m')}"
    with tqdm(total=1, desc=desc_bloco, bar_format='{desc}', leave=False) as pbar_status:
        try:
            trafego_bloco = opensky.history(start=inicio_str, stop=fim_str, bounds=area_lppt)
            
            if trafego_bloco is not None:
                resultados_do_bloco = []
                
                for voo in tqdm(trafego_bloco, desc="A calcular fisica de voos", leave=False):
                    try:
                        df = voo.data
                        if voo.callsign is None or ('altitude' not in df.columns and 'baroaltitude' not in df.columns): continue
                        col_alt = 'altitude' if 'altitude' in df.columns else 'baroaltitude'
                        df = df.dropna(subset=[col_alt])
                        if len(df) < 10: continue
                        
                        alt_min = df[col_alt].min() * (1 if col_alt == 'altitude' else 3.28084)
                        if alt_min > 2000: continue 
                        
                        df_descida = df[(df[col_alt] * (1 if col_alt == 'altitude' else 3.28084)) < 25000].copy()
                        if len(df_descida) < 60: continue 
                        
                        df_descida['timestamp'] = pd.to_datetime(df_descida['timestamp'], unit='s', utc=True)
                        df_descida.set_index('timestamp', inplace=True)
                        
                        v = df_descida['groundspeed'].ffill().bfill().fillna(150).values if 'groundspeed' in df_descida.columns else df_descida['velocity'].ffill().bfill().fillna(70).values * 1.94384
                        h = df_descida[col_alt].ffill().bfill().fillna(0).values * (1 if col_alt == 'altitude' else 3.28084)
                        v, h = np.clip(v, 100, 500), np.clip(h, 0, 40000)
                        
                        ff_mod, em_mod, mod_usado = obter_modelos(voo.typecode if hasattr(voo, 'typecode') else None)
                        massa = obter_massa_estimada(voo.typecode if hasattr(voo, 'typecode') else None)
                        
                        ff = ff_mod.enroute(mass=massa, tas=v, alt=h)
                        co2, nox = ff * 3.16, em_mod.nox(ff, tas=v, alt=h)
                        
                        dt_seg = df_descida.index.to_series().diff().dt.total_seconds().fillna(1).values
                        vs_fpm = (np.diff(h, prepend=h[0]) / dt_seg) * 60
                        
                        teve_holding = "Nao"
                        pista = "Desconhecida"
                        if 'track' in df_descida.columns:
                            diff_ang = np.where(df_descida['track'].diff().fillna(0).abs() > 180, 360 - df_descida['track'].diff().fillna(0).abs(), df_descida['track'].diff().fillna(0).abs())
                            teve_holding = "Sim" if np.sum(diff_ang) > 400 else "Nao"
                            ang = df_descida['track'].dropna().tail(10).mean()
                            if 10 <= ang <= 50: pista = "Pista 03"
                            elif 190 <= ang <= 230: pista = "Pista 21"

                        tempo_nivelado_min = np.sum(dt_seg[vs_fpm > -100]) / 60

                        resultados_do_bloco.append({
                            "Data": df_descida.index[0].strftime("%Y-%m-%d"),
                            "Hora_Aterragem": df_descida.index[-1].strftime("%H:%M:%S"),
                            "Indicativo": voo.callsign.strip(),
                            "Pista": pista,
                            "Modelo": mod_usado,
                            "Distancia_NM": round(np.sum(v * (dt_seg / 3600)), 1),
                            "Duracao_Min": round(len(df_descida) / 60, 1),
                            "Min_Nivelado": round(tempo_nivelado_min, 1),
                            "Holding_Efetuado": teve_holding,
                            "Go_Around": "Sim" if np.sum(dt_seg[(vs_fpm > 400) & (h < 4000)]) > 15 else "Nao",
                            "CO2_Total_kg": round(np.sum(co2), 2),
                            "NOx_Total_g": round(np.sum(nox), 2),
                            "NOx_LTO_Abaixo3000_g": round(np.sum(nox[h < 3000]), 2)
                        })
                    except: continue
                
                if resultados_do_bloco:
                    pd.DataFrame(resultados_do_bloco).to_csv(ficheiro_temporario, mode='a', header=not os.path.isfile(ficheiro_temporario), index=False)
            
            pbar_status.set_description_str(f"Bloco {inicio_str[:10]} concluido")
        except Exception as e: 
            pbar_status.set_description_str(f"Erro OpenSky: A aguardar para tentar de novo...")
            print(f"Erro no bloco {inicio_str}: {e}")
    
    pbar_total.update((fim_bloco - data_atual).days if fim_bloco <= data_final else (data_final - data_atual).days + 1)
    data_atual = fim_bloco
    time.sleep(15) 

pbar_total.close()

# ==========================================
# 5. FASE 2: METEOROLOGIA
# ==========================================
print("\nA integrar Meteorologia Historica (IEM ASOS)...")
try:
    url_clima = (f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=LPPT&data=tmpc&data=sknt&"
                 f"year1={ANO_ANALISE}&month1={MES_ANALISE}&day1=1&year2={ANO_ANALISE}&month2={MES_ANALISE}&day2={ultimo_dia_do_mes}&"
                 f"tz=Etc%2FUTC&format=onlycomma&latlon=no&missing=M&trace=T&direct=no")

    df_clima = pd.read_csv(url_clima, na_values=['M', 'T', ' '], on_bad_lines='skip')
    
    df_clima.columns = ['Estacao', 'Data_Hora', 'Temp_C', 'Vento_Nos']
    df_clima['Temp_C'] = pd.to_numeric(df_clima['Temp_C'], errors='coerce').ffill().bfill()
    df_clima['Vento_Nos'] = pd.to_numeric(df_clima['Vento_Nos'], errors='coerce').ffill().bfill()
    
    df_clima['Hora_Arredondada'] = pd.to_datetime(df_clima['Data_Hora']).dt.round('H')
    df_clima_agrup = df_clima.groupby('Hora_Arredondada')[['Temp_C', 'Vento_Nos']].mean().reset_index()

    df_avioes = pd.read_csv(ficheiro_temporario)
    df_avioes['Hora_Arredondada'] = pd.to_datetime(df_avioes['Data'] + ' ' + df_avioes['Hora_Aterragem']).dt.round('H')

    df_final = pd.merge(df_avioes, df_clima_agrup, on='Hora_Arredondada', how='left').drop(columns=['Hora_Arredondada'])
    df_final[['Temp_C', 'Vento_Nos']] = df_final[['Temp_C', 'Vento_Nos']].ffill().bfill()
    
    df_final.to_csv(ficheiro_final, index=False)
    os.remove(ficheiro_temporario)
    
    print("\n" + "="*60)
    print(f"SUCESSO ABSOLUTO! Base de Dados oficial criada: {ficheiro_final}")
    print("="*60)
    
except Exception as e:
    print(f"Erro no Clima: {e}. O ficheiro temporario ({ficheiro_temporario}) foi mantido para nao perder dados.")
