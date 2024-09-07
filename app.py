from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'chave_secreta'  # Necessário para usar flash messages e session

# Configuração do banco de dados
def setup_database():
    conn = sqlite3.connect('frases.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS frases
                      (id INTEGER PRIMARY KEY, frase TEXT, traducao TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico
                      (data TEXT, frase_id INTEGER)''')
    conn.commit()
    conn.close()

def get_random_frases(quantidade):
    conn = sqlite3.connect('frases.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, frase, traducao FROM frases ORDER BY RANDOM() LIMIT ?", (quantidade,))
    frases = cursor.fetchall()
    conn.close()
    return [{'id': id, 'frase': frase, 'traducao': traducao} for id, frase, traducao in frases]

def save_to_history(frase_id):
    conn = sqlite3.connect('frases.db')
    cursor = conn.cursor()
    data_atual = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO historico (data, frase_id) VALUES (?, ?)", (data_atual, frase_id))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect('frases.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT historico.data, frases.frase, frases.traducao 
                      FROM historico 
                      JOIN frases ON historico.frase_id = frases.id 
                      ORDER BY historico.data DESC, historico.rowid DESC''')
    history = cursor.fetchall()
    conn.close()
    return history

@app.route('/')
def home():
    quantidade_frases = session.get('quantidade_frases', 1)
    ultima_geracao = session.get('ultima_geracao')
    pode_gerar = True
    tempo_restante = 0
    ultima_frase = None

    if ultima_geracao:
        ultima_geracao = datetime.fromisoformat(ultima_geracao)
        agora = datetime.now()
        diferenca = agora - ultima_geracao
        if diferenca < timedelta(days=1):
            pode_gerar = False
            tempo_restante = int((timedelta(days=1) - diferenca).total_seconds())
            
            # Buscar a última frase gerada
            conn = sqlite3.connect('frases.db')
            cursor = conn.cursor()
            cursor.execute('''SELECT frases.frase, frases.traducao 
                              FROM historico 
                              JOIN frases ON historico.frase_id = frases.id 
                              ORDER BY historico.rowid DESC 
                              LIMIT 1''')
            ultima_frase = cursor.fetchone()
            conn.close()

    frases = []
    if pode_gerar:
        frases = get_random_frases(quantidade_frases)
        if frases:
            for frase in frases:
                save_to_history(frase['id'])
            session['ultima_geracao'] = datetime.now().isoformat()
            ultima_frase = (frases[-1]['frase'], frases[-1]['traducao'])

    return render_template('home.html', frases=frases, quantidade_frases=quantidade_frases, 
                           pode_gerar=pode_gerar, tempo_restante=tempo_restante, 
                           ultima_frase=ultima_frase)

@app.route('/historico')
def historico():
    history = get_history()
    return render_template('historico.html', historico=history)

@app.route('/adicionar', methods=['GET', 'POST'])
def adicionar():
    if request.method == 'POST':
        frases_texto = request.form.get('frases')
        if frases_texto:
            linhas = frases_texto.strip().split('\n')
            novas_frases = []
            for i in range(0, len(linhas) - 1, 2):
                frase = linhas[i].strip()
                traducao = linhas[i + 1].strip() if i + 1 < len(linhas) else ""
                if frase and traducao:
                    novas_frases.append((frase, traducao))
            
            if novas_frases:
                conn = sqlite3.connect('frases.db')
                cursor = conn.cursor()
                cursor.executemany("INSERT INTO frases (frase, traducao) VALUES (?, ?)", novas_frases)
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': f"{len(novas_frases)} novas frases adicionadas com sucesso!"})
            else:
                return jsonify({'success': False, 'message': "Nenhuma frase v��lida encontrada."})
        else:
            return jsonify({'success': False, 'message': "Por favor, insira algumas frases."})
    return render_template('adicionar.html')

@app.route('/get_frases')
def get_frases():
    quantidade_frases = session.get('quantidade_frases', 1)
    ultima_geracao = session.get('ultima_geracao')
    pode_gerar = True
    tempo_restante = 0

    if ultima_geracao:
        ultima_geracao = datetime.fromisoformat(ultima_geracao)
        agora = datetime.now()
        diferenca = agora - ultima_geracao
        if diferenca < timedelta(days=1):
            pode_gerar = False
            tempo_restante = int((timedelta(days=1) - diferenca).total_seconds())

    if pode_gerar:
        frases = get_random_frases(quantidade_frases)
        for frase in frases:
            save_to_history(frase['id'])
        session['ultima_geracao'] = datetime.now().isoformat()
        return jsonify({'success': True, 'frases': frases, 'tempo_restante': 86400})
    else:
        return jsonify({'success': False, 'message': 'Você só pode gerar novas frases uma vez por dia.', 'tempo_restante': tempo_restante})

@app.route('/set_quantidade_frases', methods=['POST'])
def set_quantidade_frases():
    quantidade = int(request.form.get('quantidade', 1))
    if 1 <= quantidade <= 3:
        session['quantidade_frases'] = quantidade
        return jsonify({'success': True, 'message': f'Quantidade de frases definida para {quantidade}'})
    return jsonify({'success': False, 'message': 'Quantidade inválida. Escolha entre 1 e 3.'})

@app.route('/get_frase')
def get_frase():
    frase_id, frase, traducao = get_random_frase()
    save_to_history(frase_id)
    return jsonify({'frase': frase, 'traducao': traducao})

@app.route('/limpar_historico', methods=['POST'])
def limpar_historico():
    try:
        conn = sqlite3.connect('frases.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM historico")
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Erro ao limpar histórico: {e}")
        return jsonify({'success': False})

def clear_database():
    conn = sqlite3.connect('frases.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM frases")
    cursor.execute("DELETE FROM historico")
    conn.commit()
    conn.close()

@app.route('/limpar_banco', methods=['POST'])
def limpar_banco():
    try:
        clear_database()
        return jsonify({'success': True, 'message': 'Banco de dados limpo com sucesso!'})
    except Exception as e:
        print(f"Erro ao limpar banco de dados: {e}")
        return jsonify({'success': False, 'message': 'Erro ao limpar banco de dados.'})

if __name__ == '__main__':
    setup_database()
    app.run(host='0.0.0.0', port=5000, debug=True)
