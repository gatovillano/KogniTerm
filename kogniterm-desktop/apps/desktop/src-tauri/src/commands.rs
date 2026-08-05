use tauri::command;
use crate::api_client::ApiClient;

// TODO: Use a managed state for ApiClient instead of creating new one every time
const API_URL: &str = "http://localhost:8001";

#[command]
pub async fn send_message(message: String) -> Result<String, String> {
    let client = ApiClient::new(API_URL);
    match client.send_message(message).await {
        Ok(response) => Ok(response),
        Err(e) => Err(e.to_string()),
    }
}

#[command]
pub async fn check_server_status() -> bool {
    let client = ApiClient::new(API_URL);
    client.check_health().await
}

#[command]
pub fn get_cwd() -> Result<String, String> {
    match std::env::current_dir() {
        Ok(path) => Ok(path.to_string_lossy().into_owned()),
        Err(e) => Err(e.to_string()),
    }
}

#[command]
pub fn get_api_token() -> Result<String, String> {
    if let Ok(token) = std::env::var("KOGNITERM_API_TOKEN") {
        if !token.trim().is_empty() {
            return Ok(token.trim().to_string());
        }
    }
    if let Ok(home) = std::env::var("HOME") {
        let token_path = std::path::Path::new(&home).join(".kogniterm").join("api_token");
        if let Ok(token) = std::fs::read_to_string(token_path) {
            return Ok(token.trim().to_string());
        }
    }
    Ok(String::new())
}

