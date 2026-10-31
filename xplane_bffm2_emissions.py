import pandas as pd
import numpy as np

def calcular_emissoes_bffm2(filepath):
    print(f"A iniciar analise BFFM2 do ficheiro: {filepath}...\n")
    df = pd.read_csv(filepath, sep='|', skipinitialspace=True, low_memory=False)
    df.columns = df.columns.str.strip()
    if df.columns[-1] == '':
        df = df.drop(df.columns[-1], axis=1)
        
    # Extrair Variaveis Cinematicas e Atmosfericas do X-Plane
    time = df['_real,_time']
    alt = df['__alt,ftmsl']
    ff_pph = df['___ff,__pph']
    mach = df['_Mach,ratio']
    t_amb_c = df['AMtmp,_degC'] # Temperatura ambiente real (Celsius)
    p_amb_inhg = df['AMprs,_inHG'] # Pressao ambiente real (inHg)
    
    # Isolar a Fase de Aproximacao (< 15000 ft)
    mask = alt < 15000
    time = time[mask]
    alt = alt[mask]
    ff_pph = ff_pph[mask]
    mach = mach[mask]
    t_amb_c = t_amb_c[mask]
    p_amb_inhg = p_amb_inhg[mask]
    dt = time.diff().fillna(0)
    
    if len(time) == 0:
        print("ERRO: Voo incompleto.")
        return

    # 1. Combustivel Total (kg)
    ff_kgs = (ff_pph * 0.453592) / 3600
    fuel_kg_array = ff_kgs * dt
    total_fuel_kg = fuel_kg_array.sum()
    
    # 2. Emissoes Proporcionais ao Combustivel (Estequiometria Constante)
    total_co2_kg = total_fuel_kg * 3.16
    total_h2o_kg = total_fuel_kg * 1.23   # EI de 1.23 kg por kg de Jet-A1
    total_sox_g  = total_fuel_kg * 0.84   # EI de 0.84 g por kg de Jet-A1
    
    # ==============================================================
    # BOEING FUEL FLOW METHOD 2 (BFFM2) - EQUACOES OFICIAIS
    # ==============================================================
    
    # A) Condicoes Atmosfericas (Theta e Delta)
    theta = (t_amb_c + 273.15) / 288.15
    delta = p_amb_inhg / 29.92
    
    # B) Correcao do Fuel Flow para a Referencia ao Nivel do Mar (Wf_ref)
    ff_ref_kgs = ff_kgs / (delta * (theta**3.8) * np.exp(0.2 * mach**2))
    
    # C) Base de Dados ICAO EEDB para o LEAP-1A26 (Valores de Referencia)
    #    Ordem: Idle (7%), Approach (30%), Climb-Out (85%), Take-Off (100%)
    icao_ff_ref = [0.091, 0.244, 0.710, 0.861]  # Fuel Flow (kg/s)
    icao_nox_ei = [4.61, 8.75, 13.38, 30.80]    # Indices NOx (g/kg)
    icao_co_ei  = [21.63, 2.65, 0.26, 0.24]     # Indices CO (g/kg)
    icao_hc_ei  = [0.29, 0.04, 0.02, 0.02]      # Indices HC (g/kg)
    
    # D) Interpolacao Logaritmica e Linear baseada no Fuel Flow Corrigido
    ei_nox_ref = np.interp(ff_ref_kgs, icao_ff_ref, icao_nox_ei)
    ei_co_ref  = np.interp(ff_ref_kgs, icao_ff_ref, icao_co_ei)
    ei_hc_ref  = np.interp(ff_ref_kgs, icao_ff_ref, icao_hc_ei)
    
    # E) Correcao Final dos Indices para as condicoes de voo reais
    ei_nox_real = ei_nox_ref * np.sqrt(delta**1.02 / theta**3.3)
    
    # ==============================================================
    # CALCULOS FINAIS
    total_nox_g = (fuel_kg_array * ei_nox_real).sum()
    total_co_g = (fuel_kg_array * ei_co_ref).sum()
    total_hc_g = (fuel_kg_array * ei_hc_ref).sum()
    
    # OUTPUT ACADEMICO
    print("="*55)
    print(" INVENTARIO BFFM2 (BOEING FUEL FLOW METHOD 2)")
    print("="*55)
    print(f"Tempo da Aproximacao : {time.iloc[-1] - time.iloc[0]:.1f} segundos")
    print(f"Combustivel Gasto    : {total_fuel_kg:.2f} kg")
    print("-" * 55)
    print(f"CO2 (Dioxido Carb)   : {total_co2_kg:.2f} kg")
    print(f"H2O (Vapor de Agua)  : {total_h2o_kg:.2f} kg")
    print(f"NOx (Oxidos Azoto)   : {total_nox_g:.2f} g")
    print(f"SOx (Oxidos Enxofre) : {total_sox_g:.2f} g")
    print(f"CO  (Monoxido Carb)  : {total_co_g:.2f} g")
    print(f"HC  (Hidrocarbonetos): {total_hc_g:.2f} g")
    print("="*55)

# --- EXECUCAO ---
caminho_ficheiro = r"C:\Users\berna\OneDrive\Ambiente de Trabalho\Tese\A320 simulador\LPBJCDA.txt"
calcular_emissoes_bffm2(caminho_ficheiro)
