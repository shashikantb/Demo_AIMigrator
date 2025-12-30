provider "google" {
  project = "ABC"
  region  = "us-central1"
  zone    = "us-central1-a"
}

resource "google_compute_instance" "migrated-srv821347" {
  name         = "migrated-srv821347"
  machine_type = "e2-medium"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    network = "default"

    access_config {
      # Ephemeral public IP
    }
  }

  tags = ["http-server", "https-server"]

  metadata_startup_script = file("./startup.sh")
}

resource "google_compute_firewall" "default" {
  name    = "migrated-srv821347-firewall"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "22"]
  }

  source_ranges = ["0.0.0.0/0"]
}